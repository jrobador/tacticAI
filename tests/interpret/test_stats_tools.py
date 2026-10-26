import asyncio
import json

import pytest

from tacticai.interpret.application import stats_tools as T
from tacticai.interpret.application.analyze_match import analyze
from tests.interpret.test_analysis_package import row, write

TOOLS = {"list_matches", "match_summary", "team_stats", "player_stats", "top_players", "events", "sequences", "timeline", "shot_map", "pressure_windows", "quality"}


@pytest.fixture
def root(tmp_path):
    d = tmp_path / "m1"
    d.mkdir()
    shot = dict(type="shot", team="home", player_id="home-01", x=30.0, y=0.0, end_x=54.4, end_y=0.0, speed_m_s=20.0)
    ev = [dict(type="pass", frame_index=10, t_s=1.0, clock_s=61.0, period=1, team="home", player_id="home-01", x=0.0, y=0.0, to_player_id=None, end_x=30.0, end_y=0.0,
               outcome="complete", intercepted_by=None),
          dict(type="tackle", frame_index=15, t_s=1.5, clock_s=61.5, period=1, team="away", player_id="away-01", x=-5.0, y=0.0, from_player_id="home-01"),
          dict(shot, frame_index=30, t_s=3.0, clock_s=63.0, period=1, outcome="no_goal"),
          dict(shot, frame_index=35, t_s=3.5, clock_s=63.5, period=1, outcome="goal"),
          dict(type="goal", frame_index=36, t_s=3.6, clock_s=63.6, period=1, team="home", player_id="home-01", x=54.4, y=0.0, scorer_id="home-01")]
    write(d, "meta.json", {"match_id": "m1", "teams": {"home": {"name": "H"}, "away": {"name": "A"}}, "source": {"camera_setup": "synthetic"},
                           "pitch": {"length_m": 108.8, "width_m": 70.2}, "video": {"fps": 10, "frames": 40}})
    write(d, "roster.json", {"players": [{"player_id": p["player_id"], "team": p["player_id"][:4], "name": "n-" + p["player_id"], "number": 7, "role": p["role"]} for p in row(0)["players"]]})
    write(d, "tracking.jsonl", [row(i) for i in range(40)])
    write(d, "events.jsonl", ev)
    out = analyze(str(d)) + "/events_enriched.jsonl"
    lines = [json.loads(l) for l in open(out)]
    for e in lines:
        if e["type"] == "shot":
            e["xg"] = 0.2 if e["t_s"] == 3.0 else 0.5
    write(d / "interpret", "events_enriched.jsonl", lines)
    return str(tmp_path)


def test_until_cuts_score_xg_events(root):
    full, early, mid = (T.match_summary(root, "m1", u) for u in (None, 1.2, 3.2))
    assert full["score"] == {"home": 1, "away": 0} and full["xg"]["home"] == 0.7 and full["shots"]["home"] == 2
    assert early["score"] == {"home": 0, "away": 0} and early["xg"]["home"] == 0 and early["until_t_s"] == 1.2 and early["match_id"] == "m1"
    assert mid["score"]["home"] == 0 and mid["xg"]["home"] == 0.2 and mid["shots"]["home"] == 1
    assert mid["open_play_s"] < full["open_play_s"] and "physical" in full["full_match_only"]
    assert [e["type"] for e in T.events(root, "m1", until_t_s=1.5)["events"]] == ["pass", "tackle"]
    assert T.events(root, "m1", type="shot", from_t_s=3.2)["total"] == 1 and T.events(root, "m1", limit=2)["total"] == 5


def test_team_and_player(root):
    t = T.team_stats(root, "m1", "home")
    assert (t["passes"], t["goals"], t["shots"], t["xg"]) == (1, 1, 2, 0.7) and T.team_stats(root, "m1", "away")["tackles"] == 1
    assert T.team_stats(root, "m1", "home", 0.5)["passes"] == 0
    p = T.player_stats(root, "m1", "home-01", 3.2)
    assert p["name"] == "n-home-01" and p["xg"] == 0.2 and p["goals"] == 0 and p["rating"]["scope"] == "full_match"
    assert p["physical"]["scope"] == "full_match" and p["physical"]["relative_only"] is True and "distance_rank" in p["physical"]


def test_top_players(root):
    top = T.top_players(root, "m1", "xg")
    assert top["top"][0]["player_id"] == "home-01" and top["top"][0]["value"] == 0.7 and top["scope"] == "until_t_s"
    assert T.top_players(root, "m1", "xg", until_t_s=0.5)["top"][0]["value"] == 0
    assert T.top_players(root, "m1", "distance_rank")["scope"] == "full_match"
    assert T.top_players(root, "m1", "nope")["valid"] == list(T.METRICS)


def test_lists_and_errors(root):
    assert T.list_matches(root)["matches"][0]["score"] == {"home": 1, "away": 0}
    assert len(T.shot_map(root, "m1", until_t_s=3.2)["shots"]) == 1 and T.shot_map(root, "m1", team="away")["shots"] == []
    assert all(s["end_t_s"] <= 3.2 for s in T.sequences(root, "m1", until_t_s=3.2)["sequences"])
    assert all(w["start_t_s"] <= 1 for w in T.timeline(root, "m1", until_t_s=1)["windows"])
    assert T.pressure_windows(root, "m1", "away", top=1)["windows"][0]["pressure"] is not None
    assert T.quality(root, "m1")["scope"] == "full_match"
    assert T.match_summary(root, "zz")["valid"] == ["m1"] and T.team_stats(root, "m1", "x")["valid"] == ["home", "away"]
    assert "home-01" in T.player_stats(root, "m1", "zz")["valid"]


def test_mcp_tools_registered():
    from tacticai.interpret.interfaces.mcp_server import build
    assert {t.name for t in asyncio.run(build("x").list_tools())} == TOOLS
