import json
import os

from tacticai.interpret.application.analyze_match import analyze

EVENT = {"type", "frame_index", "t_s", "clock_s", "period", "team", "player_id", "x", "y", "sequence_id", "pressure", "score_before"}
KEYS = {
    "meta.json": {"analysis_version", "match_id", "open_play_s", "projection", "calibration", "models", "thresholds", "weights"},
    "sequences.jsonl": {"sequence_id", "team", "start_t_s", "end_t_s", "start_frame", "end_frame", "start_clock_s", "period", "start_cause", "end_cause",
                        "passes", "duration_s", "start_x_att", "max_x_att", "lines_broken", "xg", "goal", "players"},
    "timeline.jsonl": {"window", "start_t_s", "end_t_s", "start_clock_s", "end_clock_s", "period", "home", "away", "momentum"},
    "quality.json": {"camera_setup", "tracking_lines", "video_frames", "main_camera_share", "ball_observed_share", "players_observed_share",
                     "mean_confidence", "gaps", "identity_swaps_suspected", "level", "notes"},
}
EVENT_KEYS = {"pass": EVENT | {"to_player_id", "end_x", "end_y", "outcome", "intercepted_by", "length_m", "progressive_m", "lines_broken", "xpass", "difficulty"},
              "shot": EVENT | {"end_x", "end_y", "speed_m_s", "outcome", "xg", "dist_goal_center_m", "visible_goal_angle_deg", "defenders_in_cone", "ball_speed_m_s", "on_target"},
              "tackle": EVENT | {"from_player_id", "zone"}}
SIDE = {"possession_share", "pressure", "xg", "final_third_entries"}
PLAYER = {"player_id", "team", "minutes_open_play", "physical", "passing", "shooting", "defending", "rating"}
BLOCKS = {"physical": {"distance_m", "distance_per_min", "distance_rank", "distance_percentile", "top_speed_m_s", "top_speed_rank", "top_speed_percentile",
                       "sprints", "sprints_per_min", "top_speed_drop_pct"},
          "passing": {"passes", "completed", "completion_pct", "mean_length_m", "progressive_passes", "lines_broken", "mean_difficulty", "passes_per_min"},
          "shooting": {"shots", "xg", "goals", "max_shot_speed_m_s"}, "defending": {"tackles", "interceptions", "pressures"},
          "rating": {"value", "unit", "scope", "breakdown", "reason"}}


def player(pid, x, role="CM"):
    return {"player_id": pid, "x": x, "y": 0.0, "vx": 1.0, "vy": 0.0, "role": role, "on_pitch": True, "observed": True, "confidence": 1.0}


def row(i):
    ps = [player("home-00", -50.0, "GK"), player("home-01", 0.0 if i < 20 else 30.5), player("away-00", 50.0, "GK"), player("away-01", 3.0)]
    return {"frame_index": i, "t_s": i / 10, "clock_s": 60 + i / 10, "period": 1, "camera": "main",
            "ball": {"x": 0.0 if i < 20 else 30.0, "y": 0.0, "z": 0.0, "vx": 0.0, "vy": 0.0, "vz": 0.0, "observed": True, "confidence": 1.0},
            "players": ps, "possession": {"team": None, "player_id": None}, "game_state": "open_play",
            "score": {"home": 0, "away": 0}, "cards": {"yellow": [], "red": []}}


def write(path, name, obj):
    with open(path / name, "w") as f:
        f.write("".join(json.dumps(o) + "\n" for o in obj) if name.endswith("l") else json.dumps(obj))


def make(tmp_path, extra=()):
    """Writes the toy match package to tmp_path (events sorted by frame, plus `extra` events)."""
    ev = [dict(type="pass", frame_index=10, t_s=1.0, clock_s=61.0, period=1, team="home", player_id="home-01", x=0.0, y=0.0, to_player_id=None, end_x=30.0, end_y=0.0,
               outcome="complete", intercepted_by=None),
          dict(type="tackle", frame_index=15, t_s=1.5, clock_s=61.5, period=1, team="away", player_id="away-01", x=-5.0, y=0.0, from_player_id="home-01"),
          dict(type="shot", frame_index=30, t_s=3.0, clock_s=63.0, period=1, team="home", player_id="home-01", x=30.0, y=0.0, end_x=54.4, end_y=0.0, speed_m_s=20.0, outcome="no_goal")]
    ev = sorted(ev + list(extra), key=lambda e: e["frame_index"])
    write(tmp_path, "meta.json", {"match_id": "m", "source": {"camera_setup": "synthetic"}, "pitch": {"length_m": 108.8, "width_m": 70.2}, "video": {"fps": 10, "frames": 40}})
    write(tmp_path, "roster.json", {"players": [{"player_id": p["player_id"], "team": p["player_id"][:4], "name": "n", "number": 1, "role": p["role"]} for p in row(0)["players"]]})
    write(tmp_path, "tracking.jsonl", [row(i) for i in range(40)])
    write(tmp_path, "events.jsonl", ev)
    return str(tmp_path)


def test_package(tmp_path):
    out = analyze(make(tmp_path))
    files = {"meta.json", "events_enriched.jsonl", "sequences.jsonl", "timeline.jsonl", "players.json", "teams.json", "quality.json", "tactical_notes.jsonl", "phases.jsonl"}
    assert set(os.listdir(out)) == files
    load = lambda n: json.load(open(os.path.join(out, n)))
    lines = lambda n: [json.loads(l) for l in open(os.path.join(out, n)) if l.strip()]
    assert load("meta.json").keys() == KEYS["meta.json"] and load("meta.json")["models"] == {"xg": None, "xpass": None, "vaep": None}
    assert load("quality.json").keys() == KEYS["quality.json"]
    for n in ("sequences.jsonl", "timeline.jsonl"):
        assert lines(n) and all(r.keys() == KEYS[n] for r in lines(n))
    assert all(r["home"].keys() == SIDE == r["away"].keys() for r in lines("timeline.jsonl"))
    got = lines("events_enriched.jsonl")
    assert [e["type"] for e in got] == ["pass", "tackle", "shot"] and all(e.keys() == EVENT_KEYS[e["type"]] for e in got)
    assert got[1]["zone"] == "mid_third" and got[0]["xpass"] is None and got[2]["xg"] is None
    pl = load("players.json")["players"]
    assert len(pl) == 4 and all(p.keys() == PLAYER and all(p[b].keys() == k for b, k in BLOCKS.items()) for p in pl)
    assert all(p["rating"]["value"] is None for p in pl) and next(p for p in pl if p["player_id"] == "home-00")["rating"]["reason"] == "saves_not_validated"
    assert next(p for p in pl if p["player_id"] == "home-01")["rating"]["reason"] == "vaep_model_missing" and load("meta.json")["models"]["vaep"] is None
    tm = load("teams.json")["teams"]
    assert [t["team"] for t in tm] == ["home", "away"] and tm[0].keys() == tm[1].keys()


def test_xg_total_never_zero_by_absence():  # review #1
    from tacticai.interpret.domain.sequences import xg_total
    assert xg_total([], True) is None and xg_total([None], True) is None and xg_total([0.2], False) is None
    assert xg_total([0.3, None], True) == 0.3 and xg_total([0.0], True) == 0.0
