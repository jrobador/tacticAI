from tacticai.interpret.domain.lines import lines_broken, opponent_lines


def pl(pid, x, role="CM"):
    return {"player_id": pid, "x": x, "y": 0.0, "role": role, "on_pitch": True}


def away_row(xs):
    """Away outfield at the given x, plus an away GK far forward and a home player, both ignored."""
    return {"players": [pl(f"away-{i:02d}", x) for i, x in enumerate(xs)] + [pl("away-99", 50, "GK"), pl("home-01", 0)]}


def ev(team, x, end_x, outcome="complete"):
    return {"type": "pass", "team": team, "x": x, "end_x": end_x, "outcome": outcome}


THREE = [10, 11, 12, 22, 23, 24, 34, 35, 36]


def test_three_lines():
    assert opponent_lines(away_row(THREE), "home") == [11, 23, 35]


def test_close_lines_merged():
    assert opponent_lines(away_row([10, 11, 12, 13, 14, 15, 34, 35, 36]), "home") == [12.5, 35]
    assert opponent_lines(away_row([10, 11, 12]), "home") == [11]
    assert opponent_lines({"players": []}, "home") == []


def test_lines_broken_home():
    r = away_row(THREE)
    assert lines_broken(ev("home", 5, 30), r) == 2  # 11 and 23
    assert lines_broken(ev("home", 5, 8), r) == 0
    assert lines_broken(ev("home", 5, 30, "intercepted"), r) == 0
    assert lines_broken({"type": "shot"}, r) == 0


def test_lines_broken_away():
    home = {"players": [pl(f"home-{i:02d}", x) for i, x in enumerate([-10, -11, -12, -22, -23, -24, -34, -35, -36])] + [pl("away-01", 0)]}
    assert opponent_lines(home, "away") == [11, 23, 35]  # away frame: x_att = -x
    assert lines_broken(ev("away", -5, -30), home) == 2
    assert lines_broken(ev("away", -30, -5), home) == 0  # backwards
