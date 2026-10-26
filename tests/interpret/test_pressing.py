import pytest

from tacticai.interpret.domain.pressure import high_press_episodes, ppda_proxy, press_outcomes, pressing_episodes, pressing_events, pressure_series, recoveries

L = 108.8


def pl(pid, x, y=0.0):
    return {"player_id": pid, "x": x, "y": y, "role": "CM", "on_pitch": True}


def rows_for(n, presser_x, carrier_x=25.0):
    return [{"frame_index": i, "t_s": i / 10, "camera": "main", "game_state": "open_play", "ball": {"x": carrier_x, "y": 0.0},
             "players": [pl("away-02", carrier_x), pl("home-03", presser_x(i))]} for i in range(n)]


def test_pressing_episodes_match_pressing_events():
    rows = rows_for(30, lambda i: 22.0 if 5 <= i < 15 else 40.0)  # home-03 within 5 m on rows 5..14 (1.0 s)
    owners = [("away", "away-02")] * 30
    eps = pressing_episodes(rows, owners)
    assert [(e["player_id"], e["team"], e["i0"], e["i1"]) for e in eps] == [("home-03", "home", 5, 14)] and eps[0]["t0"] == 0.5 and eps[0]["t1"] == 1.4
    assert pressing_events(rows, owners) == {"home-03": 1}
    assert pressing_episodes(rows, owners, min_s=1.5) == [] and pressing_episodes(rows, owners, radius_m=2.0) == []  # 3 m away is outside radius 2
    pres = pressure_series(rows, owners, "home")
    assert pres[5] == pytest.approx(1 - 3 / 5) and pres[0] == 0.0 and pressure_series(rows, owners, "away") == {}


def test_high_press_episodes_need_attacking_third_and_pressure():
    rows = rows_for(30, lambda i: 24.0)
    pres = {i: 0.8 if 10 <= i < 20 else 0.1 for i in range(30)}
    assert high_press_episodes(rows, pres, "home", L, 0.8) == [(10, 19)]
    assert high_press_episodes(rows, pres, "away", L, 0.8) == []  # for away that is its own half
    assert high_press_episodes(rows_for(30, lambda i: 24.0, carrier_x=0.0), pres, "home", L, 0.8) == []  # carrier in the middle third (xa 0 < L/6)
    assert high_press_episodes(rows, pres, "home", L, 0.8, min_s=2.0) == []


def ev(typ, team, x, **kw):
    return dict(type=typ, team=team, t_s=kw.pop("t_s", 1.0), x=x, y=0.0, **kw)


def test_recoveries_by_third_ppda_and_outcomes():
    events = [ev("tackle", "home", -40.0), ev("tackle", "home", 0.0), ev("tackle", "away", 10.0, from_player_id="home-01"),
              ev("pass", "away", 30.0, outcome="intercepted", intercepted_by="home-03", end_x=25.0, end_y=0.0),
              ev("pass", "away", 30.0, outcome="complete", intercepted_by=None, end_x=20.0, end_y=0.0),
              ev("pass", "away", 50.0, outcome="complete", intercepted_by=None, end_x=20.0, end_y=0.0),
              ev("pass", "away", -60.0, outcome="complete", intercepted_by=None, end_x=20.0, end_y=0.0),  # starts at xa -60 for home: outside the zone
              ev("pass", "home", 10.0, outcome="complete", intercepted_by=None, end_x=20.0, end_y=0.0)]
    ix = list(enumerate(events))
    r = recoveries(ix, "home", L)
    assert [(c["event_index"], c["kind"], c["third"]) for c in r] == [(0, "tackle", "def_third"), (1, "tackle", "mid_third"), (3, "interception", "att_third")]
    assert [c["event_index"] for c in recoveries(ix, "away", L)] == [2]  # away's tackle; the interception was made by home
    passes, recs = ppda_proxy(ix, r, "home", L)  # rival passes with origin xa >= -L/10: x=30 (twice) and x=50; x=-60 is out
    assert (passes, recs) == (3, 2)  # recoveries at xa 0 and 25 (xa -40 is outside the zone)
    eps = [{"t0": 0.0, "t1": 0.5}, {"t0": 5.0, "t1": 5.5}]
    assert press_outcomes(eps, [{"t_s": 3.4}]) == 1 and press_outcomes(eps, [{"t_s": 3.6}]) == 0 and press_outcomes(eps, [{"t_s": 5.2}]) == 1
