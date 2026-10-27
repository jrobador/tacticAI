from tacticai.render.domain import rundown


def ev(t, type_, team, pid, **kw):
    return {"t_s": t, "clock_s": 60 + t, "type": type_, "team": team, "player_id": pid, "score_before": {"home": 0, "away": 0}, **kw}


def test_rundown_graphics_slots_and_milestones():
    events = [ev(1, "pass", "home", "home-08", outcome="complete", lines_broken=1, xpass=0.6, length_m=20.0, to_player_id="home-09"),
              ev(2, "pass", "home", "home-08", outcome="complete", lines_broken=0, xpass=0.9),
              ev(3, "shot", "home", "home-09", outcome="no_goal", ball_speed_m_s=28.6, dist_goal_center_m=14.16, xg=0.226, on_target=False),
              ev(4, "shot", "home", "home-09", outcome="goal", ball_speed_m_s=33.4, dist_goal_center_m=17.08, xg=0.33),
              ev(4.5, "goal", "home", "home-09", scorer_id="home-09"),
              ev(6, "carry", "away", "away-04", distance_m=10.07, duration_s=2.9)]
    sprints = [{"player_id": "away-04", "team": "away", "t_s": 5.0, "clock_s": 65, "top_speed_m_s": 8.0}, {"player_id": "away-04", "team": "away", "t_s": 9.0, "clock_s": 69, "top_speed_m_s": 8.1}]
    r = rundown.build(events, sprints, lambda pid, t: 42.4, "m", lambda t: round(t + 0.8, 1))
    got = [(g["type"], g["slot"], g["t_in"]) for g in r["graphics"]]
    # the line-breaking pass only (not the routine one), the missed shot, the goal (not its shot), the second shot as a milestone,
    # the first sprint of away-04 only, the carry
    assert got == [("pass_quality", "bar", 1), ("shot", "bar", 3), ("milestone", "side", 4), ("goal", "bar", 4.5), ("player_id", "side", 5.0), ("carry", "bar", 6)]
    p, shot, _, goal, pid, _ = r["graphics"]
    assert p["data"]["completion_pct"] == 60 and p["data"]["harder_than_pct"] == 50  # harder than the other pass of the match
    assert shot["data"] == {"ball_kmh": 103, "distance_m": 14.2, "xg": 0.23, "on_target": False}
    assert goal["data"]["score"] == {"home": 1, "away": 0} and goal["t_out"] - goal["t_in"] == rundown.GOAL_ON_AIR_S
    assert goal["data"]["net_t"] == 4.8 and goal["data"]["assist_player_id"] == "home-08" and goal["t_out"] - goal["t_in"] == 4.0
    assert pid["data"] == {"top_kmh": 28.8, "distance_m": 42}
    assert [g["id"] for g in r["graphics"]][:2] == ["g000", "g001"]
