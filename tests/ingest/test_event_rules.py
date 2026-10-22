from tacticai.ingest.domain.events import DEFAULTS, extract, infer_owner, stable_owners


def fr(i, owner=None, state="open_play", score=(0, 0), ball=(0.0, 0.0), z=0.0, v=(0.0, 0.0), pos=None):
    """Contract frame; `owner` = (side, index) is placed 0.2 m from the ball, `pos` overrides {(side, index): (x, y)}."""
    pl = {("home", k): (10.0, 10.0) for k in range(11)} | {("away", k): (30.0, 30.0) for k in range(11)}
    if owner:
        pl[owner] = (ball[0] + 0.2, ball[1])
    pl |= pos or {}
    return dict(frame_index=i, t_s=i / 10, clock_s=i / 10, period=1, game_state=state,
                score=dict(home=score[0], away=score[1]),
                ball=dict(x=ball[0], y=ball[1], z=z, vx=v[0], vy=v[1], vz=0.0),
                players=[dict(player_id=f"{s}-{k:02d}", x=x, y=y, on_pitch=True) for (s, k), (x, y) in pl.items()],
                possession=dict(team=None, player_id=None))  # events must not read this


def test_infer_owner():
    f = fr(0, pos={("home", 3): (1.0, 0.0), ("away", 4): (0.0, 1.5)})
    assert infer_owner(f, 1.25, 1.5) == ("home", "home-03")  # nearest wins
    assert infer_owner(f, 0.75, 1.5) is None  # nearest is outside the radius
    assert infer_owner(fr(0, ("away", 2)), 0.5, 1.5) == ("away", "away-02")
    assert infer_owner(fr(0, ("away", 2), z=1.6), 0.5, 1.5) is None  # ball too high
    assert infer_owner(fr(0, ("away", 2), z=1.5), 0.5, 1.5) == ("away", "away-02")
    f = fr(0, ("away", 2))
    next(p for p in f["players"] if p["player_id"] == "away-02")["on_pitch"] = False
    assert infer_owner(f, 0.5, 1.5) is None  # sent-off players cannot own the ball


def test_possession_events():
    rows = [fr(0, ("home", 1)), fr(1), fr(2, ("home", 2)),                 # A->free->B: complete pass
            fr(3, ("home", 2)), fr(4), fr(5), fr(6, ("away", 3)),          # other team, gap 3: interception
            fr(7, ("away", 3), ball=(5.0, 5.0), pos={("home", 4): (5.5, 5.0)}),
            fr(8, ("home", 4), ball=(5.5, 5.0), pos={("away", 3): (5.2, 5.0)})]  # 0.3 m, gap 1: tackle
    rows += [fr(9, ("home", 4), score=(1, 0)),                              # goal
             fr(10, state="corner", score=(1, 0), pos={("home", 5): (0.0, 0.0)}),  # corner starts (break)
             fr(11, state="corner", score=(1, 0), pos={("home", 5): (0.0, 0.0)})]  # pass across the break is suppressed
    ev = extract(rows, dict(DEFAULTS, owner_min_frames=1))
    kinds = [(e["type"], e.get("outcome")) for e in ev]
    assert kinds == [("pass", "complete"), ("pass", "intercepted"), ("tackle", None), ("goal", None),
                     ("set_piece", None)], kinds
    p, i, t, g, s = ev
    assert (p["team"], p["player_id"], p["to_player_id"], p["frame_index"]) == ("home", "home-01", "home-02", 2)
    assert (i["team"], i["player_id"], i["intercepted_by"], i["end_x"]) == ("home", "home-02", "away-03", 0.0)
    assert (t["team"], t["player_id"], t["from_player_id"], t["x"]) == ("home", "home-04", "away-03", 5.5)
    assert (g["team"], g["scorer_id"], g["player_id"]) == ("home", "home-04", "home-04")
    assert (s["kind"], s["team"], s["player_id"]) == ("corner", "home", "home-05")
    assert {"type", "frame_index", "t_s", "clock_s", "period", "team", "player_id", "x", "y"} <= p.keys()


def shots(ball, v, nxt):  # slow owned row, shot onset row, next owner row
    return [e for e in extract([fr(0, ("home", 1)), fr(1, ball=ball, v=v), fr(2, nxt, ball=ball, v=v)],
                               dict(DEFAULTS, owner_min_frames=1)) if e["type"] == "shot"]


def test_real_shot():
    s = shots((32.64, 0), (27.2, 0), ("away", 0))
    assert len(s) == 1 and s[0]["team"] == "home" and s[0]["player_id"] == "home-01"
    assert s[0]["end_x"] == 54.4 and s[0]["end_y"] == 0 and s[0]["outcome"] == "no_goal"


def test_strong_pass_to_teammate_is_not_a_shot():
    assert len(shots((32.64, 0), (27.2, 0), ("home", 2))) == 0


def test_cross_wide_of_the_posts_is_not_a_shot():
    assert len(shots((43.52, 29.26), (10.88, -41.8), ("away", 0))) == 0


def test_too_far_is_not_a_shot():
    assert len(shots((10.88, 0), (27.2, 0), ("away", 0))) == 0


def test_stable_owners():
    a, b = ("home", "home-01"), ("away", "away-02")
    seq = [a, None, a, a, b, b, b, None, None, a]
    assert stable_owners(seq, 1) == seq  # min_frames=1: identity
    assert stable_owners(seq, 3) == [None, None, None, None, b, b, b, None, None, None]  # short runs dropped, run of exactly 3 kept
    assert stable_owners(seq, 2) == [None, None, a, a, b, b, b, None, None, None]
    assert stable_owners([None, None], 5) == [None, None]


def test_one_touch_shooter_survives_stabilization():
    rows = [fr(0, ("home", 1)), fr(1, ball=(32.64, 0), v=(27.2, 0)), fr(2, ball=(40.0, 0), v=(27.2, 0), score=(1, 0))]
    ev = extract(rows, dict(DEFAULTS, owner_min_frames=3))  # the 1-frame owner is a "flicker" for passes, not for shots
    shot, goal = [e for e in ev if e["type"] == "shot"], [e for e in ev if e["type"] == "goal"]
    assert len(shot) == 1 and shot[0]["player_id"] == "home-01" and shot[0]["outcome"] == "goal"
    assert goal[0]["scorer_id"] == "home-01"
