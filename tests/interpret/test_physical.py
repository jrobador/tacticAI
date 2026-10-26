import pytest

from tacticai.interpret.domain.physical import _sprints, ball_speeds, open_play_seconds, player_physical, project, team_physical


def row(f, players, state="open_play", camera="main", ball=(0, 0, 0)):
    """players: {pid: (x, y, vx, vy[, on_pitch])}; frame dt 0.1 s."""
    return {"frame_index": f, "t_s": f / 10, "camera": camera, "game_state": state,
            "ball": {"x": 0, "y": 0, "z": 0, "vx": ball[0], "vy": ball[1], "vz": ball[2]},
            "players": [{"player_id": i, "x": v[0], "y": v[1], "vx": v[2], "vy": v[3], "role": "GK" if i.endswith("00") else "CM",
                         "on_pitch": v[4] if len(v) > 4 else True} for i, v in players.items()]}


def test_gap_and_non_open_excluded():
    rows = [row(0, {"home-01": (0, 0, 1, 0)}), row(1, {"home-01": (1, 0, 1, 0)}),
            row(5, {"home-01": (50, 0, 1, 0)}), row(6, {"home-01": (51, 0, 1, 0)}),  # gap 1 -> 5: no distance
            row(7, {"home-01": (80, 0, 1, 0)}, state="corner"), row(8, {"home-01": (90, 0, 1, 0)})]
    assert open_play_seconds(rows) == pytest.approx(0.3)  # (0,1), (5,6), and 6 -> 7 (first row open)
    pl, _ = player_physical(rows, {})
    assert pl["home-01"]["distance_m"] == pytest.approx(2.0)
    assert pl["home-01"]["distance_per_min"] == pytest.approx(2.0 / (0.3 / 60))


def test_off_pitch_skipped():
    rows = [row(i, {"home-01": (i, 0, 1, 0), "home-02": (0, 0, 9, 0, False)}) for i in range(3)]
    assert "home-02" not in player_physical(rows, {})[0]


def _ts(n, fps):
    return [f / fps for f in range(n)]


@pytest.mark.parametrize("fps, frames", [(10, 10), (25, 25)])
def test_sprint_of_exactly_1s_counts_and_shorter_does_not(fps, frames):
    pad = [0] * 3
    n = lambda k: len(pad) * 2 + k
    assert _sprints(_ts(n(frames), fps), pad + [5] * frames + pad, 5) == 1
    assert _sprints(_ts(n(frames - 1), fps), pad + [5] * (frames - 1) + pad, 5) == 0  # 0.9 s at 10 fps, 0.96 s at 25 fps
    sp = [5] * (2 * fps) + [0] + [5] * frames  # one per stretch, run at the end counts
    assert _sprints(_ts(len(sp), fps), sp, 5) == 2


def test_sprint_threshold_is_p90_of_outfield_smoothed():
    rows = [row(f, {"home-00": (0, 0, 30, 0), "home-01": (0, 0, 10 if 20 <= f < 34 else 1, 0)}) for f in range(100)]  # GK speed ignored
    pl, thr = player_physical(rows, {})
    assert 1 < thr < 10 and pl["home-01"]["sprints"] == 1


def test_smoothing_is_centred_mean_of_5():
    rows = [row(f, {"home-01": (0, 0, v, 0)}) for f, v in enumerate([0, 0, 0, 0, 10, 0, 0, 0, 0])]
    assert player_physical(rows, {})[0]["home-01"]["top_speed_m_s"] == pytest.approx(2.0)


def test_rank_percentile_and_thirds_and_team():
    rows = [row(f, {"home-00": (0, 0, 0, 0), "home-01": (0, 0, 3, 0), "away-01": (0, 0, 2, 0)}) for f in range(9)]
    rows += [row(f, {"home-00": (0, 0, 0, 0), "home-01": (0, 0, 1, 0), "away-01": (0, 0, 2, 0)}) for f in range(9, 18)]
    pl, _ = player_physical(rows, {})
    assert [pl[i]["top_speed_rank"] for i in ("home-01", "away-01", "home-00")] == [1, 2, 3]
    assert [pl[i]["top_speed_percentile"] for i in ("home-01", "away-01", "home-00")] == [100, 50, 0]
    assert pl["home-01"]["top_speed_drop_pct"] > 50 and pl["away-01"]["top_speed_drop_pct"] == pytest.approx(0)
    t = team_physical(pl)
    assert t["home"]["distance_m"] == 0 and t["away"]["sprints"] == pl["away-01"]["sprints"]  # GK excluded, no motion


def test_projection():
    assert project(6.0, {"projection": {"applies": True, "effective_play_s": 3300}}) == pytest.approx(330.0)
    assert project(6.0, {"projection": {"applies": False, "effective_play_s": 3300}}) is None
    assert project(6.0, {}) == pytest.approx(330.0)


def test_ball_speeds():
    rows = [row(f, {"home-01": (0, 0, 0, 0)}, ball=(6, 8, 0)) for f in range(5)]
    ev = [{"type": "shot", "frame_index": 2, "team": "home", "player_id": "home-01", "speed_m_s": 25.0}, {"type": "pass"}]
    b = ball_speeds(rows, ev, {"calibration": {"physical_absolute": False}})
    assert b["top_speed_m_s"] == pytest.approx(10) and b["absolute"] is False
    assert b["shots"] == [{"frame_index": 2, "team": "home", "player_id": "home-01", "speed_m_s": 25.0, "ball_speed_m_s": pytest.approx(10)}]
    assert ball_speeds(rows, ev, {})["absolute"] is False


def test_shot_ball_speed_is_raw_not_smoothed():
    rows = [row(f, {"home-01": (0, 0, 0, 0)}, ball=(5, 0, 0) if f < 2 else (38, 0, 0)) for f in range(5)]
    ev = [{"type": "shot", "frame_index": 2, "team": "home", "player_id": "home-01", "speed_m_s": 40.0}]
    assert ball_speeds(rows, ev, {})["shots"][0]["ball_speed_m_s"] == pytest.approx(38)
