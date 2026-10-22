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
