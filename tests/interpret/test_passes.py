import pytest

from tacticai.interpret.domain.passes import pass_stats


def p(team, pid, x, end_x, outcome="complete", y=0, end_y=0):
    return {"type": "pass", "frame_index": 0, "team": team, "player_id": pid, "to_player_id": "z", "x": x, "y": y, "end_x": end_x,
            "end_y": end_y, "outcome": outcome}


ROWS = [{"frame_index": f, "t_s": f / 10, "camera": "main", "game_state": "open_play"} for f in range(601)]  # 60 s -> 1 min


def test_pass_stats():
    ev = [p("home", "home-01", 0, 12), p("home", "home-01", 0, 9), p("home", "home-02", 0, 12, "intercepted"),
          p("away", "away-01", 0, -12, y=0, end_y=0), p("away", "away-01", 0, 3, "intercepted", y=0, end_y=4), {"type": "shot"}]
    s = pass_stats(ev, ROWS)
    assert [q["progressive_m"] for q in s["passes"]] == [12, 9, 12, 12, -3]
    assert s["passes"][4]["length_m"] == pytest.approx(5.0)
    h, a = s["teams"]["home"], s["teams"]["away"]
    assert (h["passes"], h["completed"], h["completion_pct"], h["progressive_passes"]) == (3, 2, pytest.approx(200 / 3), 1)
    assert (a["completion_pct"], a["progressive_passes"], a["passes_per_min"]) == (50, 1, pytest.approx(2.0))
    assert s["players"]["home-01"]["mean_length_m"] == pytest.approx(10.5)


def _row(f, state="open_play", opp=(), me=(0.0, 0.0)):
    pl = lambda pid, x, y, role="CM": {"player_id": pid, "x": x, "y": y, "role": role, "on_pitch": True}
    return {"frame_index": f, "t_s": f / 10, "game_state": state, "score": {"home": 1, "away": 0},
            "players": [pl("home-01", *me, "LW")] + [pl(f"away-{i:02d}", x, y) for i, (x, y) in enumerate(opp)]}


def test_release_index_and_features():
    from tacticai.interpret.domain.frame import release_index
    from tacticai.interpret.domain.passes import pass_features
    H = ("home", "home-01")
    rows = [_row(f, opp=[(5, 1.0), (20, 0.0), (40, 9.0)]) for f in range(6)]
    owners = [H, H, H, None, None, ("home", "home-02")]
    idx = {r["frame_index"]: i for i, r in enumerate(rows)}
    e = {"type": "pass", "frame_index": 5, "t_s": 0.5, "team": "home", "player_id": "home-01", "x": 0, "y": 0, "end_x": 30, "end_y": 0, "outcome": "intercepted"}
    assert release_index(rows, owners, e, idx) == 2
    assert release_index(rows, [None] * 6, e, idx) == 5  # no owner found
    assert release_index(rows, [H, H, H, None, None, None], e, idx | {5: 5}) == 2
    stopped = rows[:2] + [rows[2] | {"game_state": "free_kick"}] + rows[3:]
    assert release_index(stopped, owners, e, idx) == 5  # the stoppage cuts the walk before the owned rows
    [f] = pass_features(rows, owners, [e, {"type": "shot"}], idx, {"match_id": "m", "pitch": {"length_m": 108.8}})
    assert (f["release_frame_index"], f["frame_index"], f["passer_role"], f["complete"], f["score_diff"]) == (2, 5, "LW", False, 1)
    assert f["opponents_near_line"] == 2 and f["nearest_opponent_to_receiver_m"] == pytest.approx(10.0) and f["lines_broken"] == 2
    assert f["length_m"] == 30 and f["progressive_m"] == 30 and f["start_third"] == "mid_third" and f["passer_pressure"] == 0
