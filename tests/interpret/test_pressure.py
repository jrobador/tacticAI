import pytest

from tacticai.interpret.domain.pressure import pressure_on, team_pressure


def pl(pid, x, y=0.0, on=True):
    return {"player_id": pid, "x": x, "y": y, "role": "CM", "on_pitch": on}


def row(players, t=0.0, state="open_play"):
    return {"frame_index": int(t * 10), "t_s": t, "camera": "main", "game_state": state, "players": players}


def test_pressure_on():
    assert pressure_on(row([pl("home-01", 0)]), "home-01") == 0.0
    assert pressure_on(row([pl("home-01", 0), pl("away-01", 2.5)]), "home-01") == pytest.approx(0.5)
    assert pressure_on(row([pl("home-01", 0), pl("away-01", 1), pl("away-02", 0, 1), pl("away-03", 2)]), "home-01") == 1.0  # capped
    assert pressure_on(row([pl("home-01", 0), pl("away-01", 6), pl("away-02", 2.5, on=False)]), "home-01") == 0.0
    assert pressure_on(row([pl("home-01", 0, on=False), pl("away-01", 1)]), "home-01") == 0.0
    assert pressure_on(row([pl("away-01", 0), pl("home-01", 2.5), pl("home-02", 0, 4)]), "away-01") == pytest.approx(0.5 + 0.2)


def test_team_pressure():
    ps = [pl("home-01", 0), pl("away-01", 2.5)]
    rows = [row(ps, t=i / 10) for i in range(4)] + [row(ps, t=0.4, state="corner")]
    own = [("home", "home-01"), ("home", "home-01"), ("away", "away-01"), None, ("home", "home-01")]
    assert team_pressure(rows, own, "away") == pytest.approx(0.5)  # rows 0, 1 (row 4 is not open play)
    assert team_pressure(rows, own, "away", t0=0.1) == pytest.approx(0.5)
    assert team_pressure(rows, own, "away", t0=0.1, t1=0.1) is None
    assert team_pressure(rows, own, "home") == pytest.approx(0.5)  # row 2
