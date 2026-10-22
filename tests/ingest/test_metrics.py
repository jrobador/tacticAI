from tacticai.ingest.domain.metrics import (all_metrics, block_height, defensive_line_height, mean_pass_length_m,
                                            possession_pct, recoveries_opp_half_per_min, team_length, team_width)

HALF = 54.4


def row(owner, home, away):
    """home/away: [(x, y)] with the first player the GK. owner: "home" / "away" / None."""
    pl = lambda side, t: [{"player_id": f"{side}-{i:02d}", "x": x, "y": y, "role": "GK" if i == 0 else "CB", "on_pitch": True}
                          for i, (x, y) in enumerate(t)]
    return {"possession": {"team": owner, "player_id": None}, "players": pl("home", home) + pl("away", away)}


L = [(-54.4, 0), (-40, -10), (-40, 10), (-30, -5), (-30, 5), (-10, 0)]  # forward = x + 54.4
R = [(54.4, 0), (40, -20), (40, 20), (30, 0), (20, 0), (0, 0)]  # forward = 54.4 - x
ROWS = [row("away", L, R), row("away", L, R), row("home", L, R), row(None, L, R)]


def test_shape_metrics():
    f = lambda *xs: sum(x + HALF for x in xs) / len(xs)
    assert defensive_line_height(ROWS, "home", HALF) == f(-40, -40, -30, -30)  # away owns 2 rows, GK excluded
    assert block_height(ROWS, "home", HALF) == f(-40, -40, -30, -30, -10)
    assert block_height(ROWS, "home", HALF, True) == block_height(ROWS, "home", HALF)  # same positions every row
    assert team_length(ROWS, "home", HALF) == 30 and team_width(ROWS, "home", HALF) == 20
    assert team_width(ROWS, "away", HALF) == 40 and team_length(ROWS, "away", HALF) == 40
    assert defensive_line_height([row("home", L, R)], "home", HALF) is None  # never defending -> no value


def test_away_forward_is_negative_x():
    assert defensive_line_height([row("home", L, R)], "away", HALF) == (14.4 + 14.4 + 24.4 + 34.4) / 4


def test_possession():
    assert possession_pct(ROWS, "home") == 25 and possession_pct(ROWS, "away") == 50


def ev(typ, team, end, **kw):
    return dict(type=typ, team=team, x=end[0] if typ == "tackle" else 0, y=0, end_x=end[0], end_y=end[1], **kw)


def test_events():
    rows = [row("home", L, R)] * 600  # 60 s
    events = [ev("tackle", "home", (10, 0)), ev("tackle", "home", (-10, 0)),
              ev("pass", "away", (5, 0), outcome="intercepted"),  # intercepted by home
              ev("pass", "home", (30, 0), outcome="complete"), ev("pass", "home", (0, 40), outcome="complete"),
              ev("pass", "away", (-50, 0), outcome="complete")]
    assert recoveries_opp_half_per_min(rows, events, "home") == 2
    assert recoveries_opp_half_per_min(rows, events, "away") == 0
    assert mean_pass_length_m(events, "home") == 35 and mean_pass_length_m(events, "away") == 50
    assert all_metrics(rows, events, "home", HALF)["possession_pct"] == 100


def test_aggregate():
    from tacticai.ingest.application.measure_presets import aggregate
    r = aggregate([("a", {"x": 1.0, "y": None}), ("a", {"x": 3.0, "y": None})])
    assert r["a"]["x"] == {"mean": 2.0, "std": 1.0, "n": 2} and r["a"]["y"] is None
