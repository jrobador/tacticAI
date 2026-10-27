import json

from tacticai.render.application import reels as R


def g(gid, kind, t_in=10.0, t_out=15.0, **data):
    return {"id": gid, "type": kind, "t_in": t_in, "t_out": t_out, "team": "home", "player_id": "home-09", "data": data}


def test_only_goals_and_shots_make_reels():
    gs = [g("g0", "goal"), g("g1", "carry"), g("g2", "shot"), g("g3", "player_id")]
    assert [x["id"] for x in R.select(gs)] == ["g0", "g2"]


def test_interval_starts_before_and_is_clamped_to_the_video():
    assert R.interval(10.0, 15.0, 36.9) == (7.0, 15.0)
    assert R.interval(1.0, 6.0, 36.9) == (0.0, 6.0)
    assert R.interval(30.0, 38.0, 36.9) == (27.0, 36.9)


def test_crop_center_follows_the_ball_only_far_from_the_middle():
    assert [R.crop_center(x) for x in (0, 29.9, 40, -40)] == [0.5, 0.5, 0.72, 0.28]
    assert R.ball_x("/no/such/match", 1.0) is None


def test_goal_interval_is_around_the_late_graphic_and_ball_pick_is_max_abs_x():
    assert R.interval(24.3, 29.0, 36.9, "goal") == (18.3, 25.8)
    assert R.interval(24.3, 29.0, 36.9, "shot") == (21.3, 29.0)
    rows = [{"t_s": t, "ball": {"x": x}} for t, x in ((17.0, 60.0), (20.0, -10.0), (23.0, 54.2), (24.3, 2.0), (25.0, -70.0))]
    assert R.pick_ball_x(rows, 24.3) == 54.2 and R.pick_ball_x(rows, 100.0) is None


def test_cells_use_decimal_comma_in_spanish():
    shot = g("g2", "shot", ball_kmh=103, distance_m=14.2, xg=0.23)
    assert R.cells(shot, False) == [("103", "km/h", "Ball speed"), ("14.2", "m", "Distance"), ("0.23", "", "xG")]
    assert R.cells(shot, True)[1] == ("14,2", "m", "Distancia")


def test_lower_third_draws_without_a_face():
    teams = {"home": {"name": "Brackenford Athletic", "short": "BKA"}, "away": {"name": "Wexmoor City", "short": "WXC"}}
    goal = g("g0", "goal", score={"home": 1, "away": 0}, ball_kmh=120, distance_m=17.1)
    assert R.lower_third(goal, False, "CORLUNE", teams).size[0] <= R.W - 2 * R.LT_X


def test_missing_video_is_recorded_not_raised(tmp_path):
    warnings = R.run(str(tmp_path))
    m = json.loads((tmp_path / "render" / "reels" / "manifest.json").read_text(encoding="utf-8"))
    assert m["reels"] == [] and m["errors"][0]["message"] == "no video.mp4" and warnings == ["reels: no video.mp4"]
