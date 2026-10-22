from tacticai.ingest.domain.events import DEFAULTS, extract


def make_row(i, team=-1, pl=-1, mode=0, score=(0, 0), pos=None):
    L = [[10.0, 10.0] for _ in range(11)]
    R = [[30.0, 30.0] for _ in range(11)]
    for (tm, p), xy in (pos or {}).items():
        (L if tm == 0 else R)[p] = xy
    return dict(step=i, frame_index=i, engine_time_s=i / 10, match_time_s=i / 10, ball=[0, 0, 0],
                ball_direction=[0, 0, 0], ball_owned_team=team, ball_owned_player=pl, left_team_eng=L,
                right_team_eng=R, ball_eng=[0, 0, 0], ball_m=[0, 0, 0], score=list(score), game_mode=mode)


def test_possession_events():
    close = {(1, 3): [5.0, 5.0], (0, 4): [5.5, 5.0]}
    rows = [make_row(0, 0, 1), make_row(1), make_row(2, 0, 2),             # A->free->B: complete pass
    make_row(3, 0, 2), make_row(4), make_row(5), make_row(6, 1, 3),     # other team, far, gap 3: interception
    make_row(7, 1, 3, pos=close), make_row(8, 0, 4, pos=close)]  # 0.5 m, gap 1: tackle
    rows += [make_row(9, 0, 4, score=(1, 0)),                    # goal
     make_row(10, -1, -1, mode=4, score=(1, 0), pos={(0, 5): [0.0, 0.0]}),         # corner starts (break)
     make_row(11, -1, -1, mode=4, score=(1, 0), pos={(0, 5): [0.0, 0.0]})]           # pass across the break is suppressed
    ev = extract(rows, dict(DEFAULTS))
    kinds = [(e["type"], e.get("outcome")) for e in ev]
    assert kinds == [("pass", "complete"), ("pass", "intercepted"), ("tackle", None), ("goal", None),
                     ("set_piece", None)], kinds
    assert ev[-1]["kind"] == "corner" and ev[-1]["team"] == 0 and ev[-1]["player"] == 5 and ev[2]["team"] == 0


def shot_row(i, owner=-1, pl=-1, ball=(0, 0), d=(0, 0)):
    r = make_row(i, owner, pl)
    r["ball"], r["ball_direction"] = [ball[0], ball[1], 0], [d[0], d[1], 0]
    return r


def shots(ball, d, nxt):  # slow owned row, shot onset row, next owner row
    return [e for e in extract([shot_row(0, 0, 1), shot_row(1, ball=ball, d=d), shot_row(2, *nxt)], dict(DEFAULTS))
            if e["type"] == "shot"]


def test_real_shot():
    assert len(shots((0.6, 0), (0.05, 0), (1, 0))) == 1


def test_strong_pass_to_teammate_is_not_a_shot():
    assert len(shots((0.6, 0), (0.05, 0), (0, 2))) == 0


def test_cross_wide_of_the_posts_is_not_a_shot():
    assert len(shots((0.8, 0.35), (0.02, -0.05), (1, 0))) == 0


def test_too_far_is_not_a_shot():
    assert len(shots((0.2, 0), (0.05, 0), (1, 0))) == 0
