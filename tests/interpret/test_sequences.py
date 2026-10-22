from tacticai.interpret.domain.sequences import sequences

H, A = ("home", "home-01"), ("away", "away-01")


def mk(owners, states=None, frames=None, scores=None, periods=None):
    n = len(owners)
    frames = frames or list(range(n))
    rows = [{"frame_index": f, "t_s": f / 10, "clock_s": 100 + f / 10, "period": (periods or [1] * n)[i], "camera": "main",
             "game_state": (states or ["open_play"] * n)[i], "score": (scores or [{"home": 0, "away": 0}] * n)[i],
             "ball": {"x": float(i)}, "players": []} for i, f in enumerate(frames)]
    return rows, owners


def test_lost_recovery_and_loose_ball():
    rows, o = mk([H, H, None, None, A, A, A])
    ev = [{"type": "tackle", "team": "away", "t_s": 0.4, "frame_index": 4}]
    s, ids = sequences(rows, ev, o)
    assert [(q["team"], q["start_frame"], q["end_frame"]) for q in s] == [("home", 0, 3), ("away", 4, 6)]  # loose rows stay with home
    assert (s[0]["start_cause"], s[0]["end_cause"], s[1]["start_cause"], s[1]["end_cause"]) == ("kick_off", "lost", "recovery", "end_of_period")
    assert s[0]["duration_s"] == 0.3 and s[0]["players"] == ["home-01"] and s[1]["max_x_att"] == -4.0 and s[1]["start_x_att"] == -4.0
    assert ids == [1]
    assert sequences(rows, [], o)[0][1]["start_cause"] == "loose_ball"


def test_loose_ball_does_not_split():
    rows, o = mk([H, None, None, H])
    s, _ = sequences(rows, [], o)
    assert len(s) == 1 and (s[0]["start_frame"], s[0]["end_frame"]) == (0, 3)


def test_set_piece_start():
    rows, o = mk([H, H, None, None, None, A, A], states=["open_play"] * 2 + ["throw_in"] * 3 + ["open_play"] * 2)
    s, _ = sequences(rows, [], o)
    assert [q["end_cause"] for q in s] == ["out", "end_of_period"]
    assert (s[0]["end_frame"], s[1]["start_frame"], s[1]["start_cause"]) == (1, 5, "set_piece:throw_in")


def test_goal_end_and_kick_off():
    sc = [{"home": 0, "away": 0}] * 3 + [{"home": 1, "away": 0}] * 4
    rows, o = mk([H, H, H, None, None, A, A], scores=sc)
    s, ids = sequences(rows, [{"type": "shot", "team": "home", "frame_index": 1}, {"type": "goal", "team": "home", "frame_index": 3}], o)
    assert (s[0]["end_cause"], s[0]["goal"], s[0]["end_frame"], s[1]["start_cause"]) == ("goal", True, 2, "kick_off")
    assert ids == [0, None]


def test_frame_gap_splits():
    rows, o = mk([H] * 6, frames=[0, 1, 2, 10, 11, 12])
    s, ids = sequences(rows, [{"type": "pass", "team": "home", "frame_index": f, "outcome": "complete", "x": 0, "end_x": 1} for f in (1, 5, 11)], o)
    assert [(q["start_frame"], q["end_frame"], q["end_cause"], q["start_cause"]) for q in s] == [(0, 2, "out", "kick_off"), (10, 12, "end_of_period", "loose_ball")]
    assert ids == [0, None, 1] and (s[0]["passes"], s[1]["passes"]) == (1, 1)


def test_period_change_and_event_ids():
    rows, o = mk([H, H, A, A, A], periods=[1, 1, 1, 2, 2])
    ev = [{"type": "shot", "team": "home", "frame_index": 1, "t_s": 0.1},
          {"type": "pass", "team": "home", "frame_index": 2, "t_s": 0.2, "outcome": "intercepted", "intercepted_by": "away-01", "x": 0, "end_x": 1}]
    s, ids = sequences(rows, ev, o)
    assert [(q["team"], q["end_cause"], q["period"]) for q in s] == [("home", "shot", 1), ("away", "end_of_period", 1), ("away", "end_of_period", 2)]
    assert s[2]["start_cause"] == "kick_off" and s[0]["passes"] == 1 and ids == [0, 0]
