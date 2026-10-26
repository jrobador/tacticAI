import json
import os

import pytest

from tacticai.interpret.application.analyze_match import analyze
from tacticai.interpret.application.tactics_tools import COMPARE, Tactics, load_match
from tests.interpret.test_analysis_package import row as static_row, write

L, W = 108.8, 70.2
BASE = {"home-00": (-50.0, 0.0, "GK"), "home-01": (-30.0, -10.0, "CB"), "home-02": (-20.0, 0.0, "CM"), "home-03": (-10.0, 10.0, "CF"),
        "away-00": (50.0, 0.0, "GK"), "away-01": (30.0, 10.0, "CB"), "away-02": (20.0, 0.0, "CM"), "away-03": (10.0, -10.0, "CF")}
SWAP = lambda pid: ("away" if pid.startswith("home") else "home") + pid[4:]


def make_rows(n, owner_of=lambda i: "away-03", shift_of=lambda i: 0.0, over=None, mirror=False):
    """n open-play rows at 10 fps. Home outfield x moves by shift_of(i); over(i) -> {player_id: (x, y)} overrides; the ball sits on its owner (loose at (0, 30) when None).
    mirror: the same match seen with home and away swapped (ids, ball owner and score swapped, x and y negated)."""
    rows = []
    for i in range(n):
        pos = {k: [v[0] + (shift_of(i) if k.startswith("home") and v[2] != "GK" else 0.0), v[1]] for k, v in BASE.items()}
        pos.update({k: list(v) for k, v in (over(i) if over else {}).items()})
        own = owner_of(i)
        bx, by = pos[own] if own else (0.0, 30.0)
        ps = []
        for pid, (x, y) in pos.items():
            ps.append({"player_id": SWAP(pid) if mirror else pid, "x": -x if mirror else x, "y": -y if mirror else y, "vx": 0.0, "vy": 0.0, "role": BASE[pid][2],
                       "on_pitch": True, "observed": True, "confidence": 1.0})
        rows.append({"frame_index": i, "t_s": i / 10, "clock_s": 60 + i / 10, "period": 1, "camera": "main",
                     "ball": {"x": -bx if mirror else bx, "y": -by if mirror else by, "z": 0.0, "vx": 0.0, "vy": 0.0, "vz": 0.0, "observed": True, "confidence": 1.0},
                     "players": ps, "possession": {"team": None, "player_id": None}, "game_state": "open_play", "score": {"home": 0, "away": 0}, "cards": {"yellow": [], "red": []}})
    return rows


def tackle(frame, team, pid, x, frm):
    return dict(type="tackle", frame_index=frame, t_s=frame / 10, clock_s=60 + frame / 10, period=1, team=team, player_id=pid, x=x, y=0.0, from_player_id=frm)


def package(path, rows, events=()):
    """Writes a match package, runs analyze and returns (match dir, Tactics)."""
    path.mkdir(exist_ok=True)
    write(path, "meta.json", {"match_id": "m", "source": {"camera_setup": "synthetic"}, "pitch": {"length_m": L, "width_m": W}, "video": {"fps": 10, "frames": len(rows)}})
    write(path, "roster.json", {"players": [{"player_id": p["player_id"], "team": p["player_id"][:4], "name": "n-" + p["player_id"], "number": 1, "role": p["role"]} for p in rows[0]["players"]]})
    write(path, "tracking.jsonl", rows)
    write(path, "events.jsonl", list(events))
    analyze(str(path))
    return str(path), Tactics(load_match(str(path)))


def varied(i):
    return 10.0 * ((i // 50) % 4)


@pytest.fixture
def long_match(tmp_path):
    return package(tmp_path / "long", make_rows(300, shift_of=varied))[1]


COMMON = {"from_t_s", "until_t_s", "parameters", "thresholds_used", "sample", "sufficient_evidence", "limitations", "evidence", "results"}


def test_common_response_and_symmetry(tmp_path, long_match):
    r = long_match.team_shape(team="home", in_possession=False, metrics=["block_height", "defensive_line"])
    assert r.keys() == COMMON and r["evidence"].keys() == {"event_indices", "sequence_ids", "timeline_windows", "frame_ranges"}
    assert r["sample"].keys() == {"eligible_s", "owned_s", "opponent_owned_s", "loose_s", "n_events"} and r["sample"]["opponent_owned_s"] == pytest.approx(29.9)
    res = r["results"]["home"]
    flat = long_match.team_shape(team="home", in_possession=False, metrics=["length"])  # length is constant in this fixture: flat dispersion
    assert flat["sufficient_evidence"] is False and flat["results"]["home"]["length"]["band"] is None
    assert r["sufficient_evidence"] is True and res["block_height"]["n_windows"] == 6 and res["block_height"]["band"] in ("high_relative", "typical", "low_relative")
    # first 4 s: shift 0 -> hand geometry (outfield xa -30, -20, -10; h = xa + L/2; ya -10, 0, 10)
    first = long_match.team_shape(team="home", until_t_s=4.0, in_possession=False)["results"]["home"]
    assert first["block_height"]["value"] == pytest.approx(34.4) and first["defensive_line"]["value"] == pytest.approx(34.4)
    assert first["length"]["value"] == pytest.approx(20.0) and first["width"]["value"] == pytest.approx(20.0)
    assert first["block_height"]["band"] == "low_relative" and first["block_height"]["percentile"] == pytest.approx(100 / 6, abs=0.01)
    # same match with home and away swapped: the same values for the swapped team
    mirror = package(tmp_path / "mirror", make_rows(300, shift_of=varied, mirror=True))[1]
    a = long_match.team_shape(team="home", in_possession=False)["results"]["home"]
    b = mirror.team_shape(team="away", in_possession=False)["results"]["away"]
    assert a == b
    both = long_match.team_shape(in_possession=None)
    assert set(both["results"]) == {"home", "away"} and set(both["sample"]) == {"home", "away"}


def test_relative_guards(tmp_path):
    flat = package(tmp_path / "flat", make_rows(300))[1].team_shape(team="home", in_possession=False)
    h = flat["results"]["home"]["block_height"]
    assert flat["sufficient_evidence"] is False and h["value"] == pytest.approx(34.4) and h["band"] is None and h["percentile"] is None and "flat" in h["relative_reason"]
    short = package(tmp_path / "short", make_rows(60, shift_of=varied))[1].team_shape(team="home", in_possession=False)
    h = short["results"]["home"]["block_height"]
    assert short["sufficient_evidence"] is False and h["band"] is None and h["n_windows"] < 4 and "fewer than 4" in h["relative_reason"]
    assert short["results"]["home"]["occupation"]["cells"] is not None  # descriptive metrics stay available


def test_occupation_and_block_band(long_match):
    r = long_match.team_shape(team="home", until_t_s=4.0, in_possession=False, metrics=["occupation", "block_band"])["results"]["home"]
    cells = r["occupation"]["cells"]
    # home-01 (xa -30, ya -10), home-02 (-20, 0), home-03 (-10, 10); lane cuts at +-7.02 and +-21.06
    assert (cells["def_third"]["half_left"]["mean_players"], cells["def_third"]["center"]["mean_players"], cells["mid_third"]["half_right"]["mean_players"]) == pytest.approx((1.0, 1.0, 1.0))
    assert sum(c["player_s"] for t in cells.values() for c in t.values()) == pytest.approx(3 * 4.0) and r["block_band"]["band"] == "low_relative"
    eps = r["block_band"]["low_block_candidates"]
    assert len(eps) == 1 and eps[0]["from_t_s"] == 0.0 and eps[0]["duration_s"] >= 2.0 and eps[0]["mean_block_height"] == pytest.approx(34.4)
    assert long_match.team_shape(team="home", in_possession=True, metrics=["block_band"])["results"]["home"]["block_band"]["candidates_reason"] == "not_defending"


def test_nulls_without_models(tmp_path):
    shot = dict(type="shot", frame_index=20, t_s=2.0, clock_s=62.0, period=1, team="home", player_id="home-03", x=30.0, y=0.0, end_x=54.4, end_y=0.0, speed_m_s=20.0, outcome="no_goal")
    t = package(tmp_path / "shot", make_rows(60), [shot])[1]
    xg = t.match_context()["results"]["home"]["xg"]
    assert xg["value"] is None and xg["reason"] == "no_model" and xg["shots"] == 1
    none = package(tmp_path / "noshot", make_rows(60))[1].match_context()["results"]["home"]["xg"]
    assert none["value"] is None and none["reason"] == "no_shots"
    ctx = t.match_context()
    assert ctx["results"]["match"]["score"] == {"home": 0, "away": 0} and ctx["results"]["home"]["possession_pct"]["value"] == 0.0 and ctx["evidence"]["event_indices"] == [0]
    away = ctx["results"]["away"]["possession_pct"]["value"]
    assert away == pytest.approx(100.0)
    assert t.match_context(until_t_s=-1.0)["results"]["home"]["possession_pct"] == {"value": None, "reason": "no_owned_time"}


def test_errors(long_match):
    assert long_match.team_shape(team="x")["error"].startswith("unknown team")
    assert long_match.team_shape(metrics=["foo"])["valid"] and long_match.pressing_profile(metrics=["foo"])["valid"]
    assert long_match.match_context(score_state="up")["valid"] == ["all", "leading", "drawing", "trailing"]
    assert long_match.compare_metrics(["nope"], "home", {})["error"] and long_match.player_profile(player_id="x-1")["error"]
    assert long_match.possession_analysis(metrics=["counterpress"])["error"]


def test_compare_metrics_numbers_come_from_tools(long_match):
    a = {"from_t_s": 0.0, "until_t_s": 4.0}
    b = {"from_t_s": 15.0, "until_t_s": 19.0}
    r = long_match.compare_metrics(["block_height", "width", "pressure"], "home", a, b, in_possession=False)
    ta = long_match.team_shape(team="home", **a, in_possession=False, metrics=["block_height"])["results"]["home"]["block_height"]
    tb = long_match.team_shape(team="home", **b, in_possession=False, metrics=["block_height"])["results"]["home"]["block_height"]
    bh = r["results"]["home"]["block_height"]
    assert bh["a"]["value"] == ta["value"] and bh["b"]["value"] == tb["value"] and bh["a"]["percentile"] == ta["percentile"] and bh["a"]["match_max"] == ta["max"]
    assert bh["diff"] == round(ta["value"] - tb["value"], 3) and bh["ratio"] == round(ta["value"] / tb["value"], 3)
    assert bh["pct_change"] == round(100 * (ta["value"] - tb["value"]) / tb["value"], 3) and bh["change_pts"] is None
    # no data -> null with a reason, never 0 (pressure is 0.0 here because nobody presses; width has a value)
    assert r["results"]["home"]["width"]["diff"] is not None and r["sample"].keys() == {"a", "b"}
    # reference = whole match for the same team
    m = long_match.compare_metrics(["block_height"], "home", a, in_possession=False)["results"]["home"]["block_height"]
    full = long_match.team_shape(team="home", metrics=["block_height"], in_possession=False)["results"]["home"]["block_height"]
    assert m["b"]["value"] == full["value"]
    opp = long_match.compare_metrics(["possession_pct"], "home", a, reference="opponent")["results"]["home"]["possession_pct"]
    assert opp["a"]["value"] == 0.0 and opp["b"]["value"] == 100.0 and opp["change_pts"] == -100.0
    assert set(COMPARE) >= {"block_height", "pressure", "ppda_proxy", "xg"}
    missing = long_match.compare_metrics(["xg"], "home", a)["results"]["home"]["xg"]
    assert missing["diff"] is None and missing["a"]["reason"] == "no_shots"


def counter_match(tmp_path):
    over = lambda i: {"home-02": (min(34.0, -20.0 + (i - 50) * 1.8), 0.0)} if i >= 50 else {}
    rows = make_rows(150, owner_of=lambda i: "away-02" if i < 50 else "home-02", over=over)
    return package(tmp_path / "counter", rows, [tackle(50, "home", "home-02", -20.0, "away-02")])


def test_possession_analysis_and_phases(tmp_path):
    d, t = counter_match(tmp_path)
    r = t.possession_analysis(team="home")
    res = r["results"]["home"]
    assert res["counters"]["count"] == 1 and res["counters"]["items"][0]["gain_m"] == pytest.approx(54.0) and res["attacking_transitions"]["count"] == 1
    assert res["possessions"]["n"] == 1 and res["build_up"]["count"] == 1 and res["build_up"]["items"][0]["outcome"] == "exited_third"
    pc = res["phase_candidates"]
    assert pc["count"] == 2 and pc["items"][1]["phase"] == "counter" and pc["items"][1]["candidate_id"] == 2 and pc["items"][1]["from_t_s"] == 5.0
    away = t.possession_analysis(team="away")["results"]["away"]
    assert away["defensive_transitions"]["items"][0]["opponent_gain_m"] == pytest.approx(54.0) and away["defensive_transitions"]["items"][0]["regained"] is False
    assert away["phase_candidates"]["items"][0]["phase"] == "build_up" and away["counters"]["count"] == 0
    assert r["evidence"]["sequence_ids"] and r["evidence"]["event_indices"] == [0]
    # a restricted interval keeps what overlaps it, with the covered part; the end is exclusive
    cut = t.possession_analysis(team="home", until_t_s=8.0, metrics=["counters"])["results"]["home"]["counters"]
    assert cut["count"] == 1 and cut["items"][0]["covered_s"] == pytest.approx(3.0) and cut["items"][0]["until_t_s"] == 10.0
    assert t.possession_analysis(team="home", until_t_s=5.0, metrics=["counters"])["results"]["home"]["counters"]["count"] == 0


def test_phase_candidates_missing_file(tmp_path):
    d, _ = counter_match(tmp_path)
    os.remove(os.path.join(d, "interpret", "phases.jsonl"))
    r = Tactics(load_match(d)).possession_analysis(team="home", metrics=["phase_candidates"])
    assert r["results"]["home"]["phase_candidates"]["reason"] == "phases.jsonl not found" and r["sufficient_evidence"] is False


def test_pressing_profile(tmp_path):
    # home-03 presses the away owner (25, 0) from 1 m for 3 s, then the owner is released; one home tackle at the end
    over = lambda i: {"away-02": (25.0, 0.0), "home-03": (24.0, 0.0)} if i < 30 else {"away-02": (25.0, 0.0), "home-03": (-10.0, 10.0)}
    ev = [tackle(40, "home", "home-03", 30.0, "away-02")]
    t = package(tmp_path / "press", make_rows(60, owner_of=lambda i: "away-02", over=over), ev)[1]
    r = t.pressing_profile(team="home")
    res = r["results"]["home"]
    assert res["pressures"]["count"] == 1 and res["pressures"]["per_min"] == pytest.approx(1 / (5.9 / 60), abs=1e-3)
    assert res["recoveries"] == {"total": 1, "def_third": 0, "mid_third": 0, "att_third": 1, "reason": None} and res["high_regains"]["count"] == 1
    assert res["press_outcomes"]["episodes"] == 1 and res["press_outcomes"]["rate"] == 1.0
    assert res["pressure"]["value"] == pytest.approx(24 / 59, abs=1e-3) and res["pressure"]["band"] is None
    assert res["high_press"]["count"] is None and res["high_press"]["reason"] and r["sufficient_evidence"] is False
    assert res["ppda_proxy"]["value"] == 0.0 and res["ppda_proxy"]["own_recoveries"] == 1 and res["ppda_proxy"]["opponent_passes"] == 0
    # away never pressed anybody: counts are real zeros, ratios are null with a reason
    a = t.pressing_profile(team="away", metrics=["pressures", "press_outcomes", "ppda_proxy"])["results"]["away"]
    assert a["pressures"]["count"] == 0 and a["press_outcomes"]["rate"] is None and a["press_outcomes"]["reason"] == "no_press_episodes"
    assert a["ppda_proxy"]["value"] is None and a["pressures"]["per_min"] is None


def test_tactical_evidence_and_player_profile(tmp_path):
    d, t = counter_match(tmp_path)
    notes = [{"t_s": 0.0, "until_t_s": 5.0, "start_clock_s": 60.0, "period": 1, "team": "away", "kind": "pressure_peak", "text_key": "k", "strength": 0.5, "evidence": {"timeline_windows": [0]}},
             {"t_s": 6.0, "until_t_s": 9.0, "start_clock_s": 66.0, "period": 1, "team": "home", "kind": "dominance_spell", "text_key": "k", "strength": 0.4, "evidence": {"timeline_windows": [1]}}]
    with open(os.path.join(d, "interpret", "tactical_notes.jsonl"), "w") as f:
        f.writelines(json.dumps(n) + "\n" for n in notes)
    t = Tactics(load_match(d))
    r = t.tactical_evidence(team="home", kind="notes")
    assert [n["note_index"] for n in r["results"]["all"]["notes"]["items"]] == [1] and r["results"]["all"]["notes"]["total"] == 1
    allk = t.tactical_evidence()
    assert set(allk["results"]["all"]) == {"notes", "events", "sequences", "windows"} and allk["results"]["all"]["notes"]["total"] == 2
    page = t.tactical_evidence(kind="sequences", limit=1)
    assert len(page["results"]["all"]["sequences"]["items"]) == 1 and page["results"]["all"]["sequences"]["next_cursor"] == 1
    assert t.tactical_evidence(kind="sequences", limit=1, cursor=1)["results"]["all"]["sequences"]["next_cursor"] is None
    ev = t.tactical_evidence(kind="events", event_type="tackle")["results"]["all"]["events"]
    assert ev["total"] == 1 and ev["items"][0]["event_index"] == 0
    pj = t.player_profile(team="home", rank_by="rating", limit=3)
    items = pj["results"]["home"]
    assert len(items) == 3 and all(i["rating"]["scope"] == "full_match" for i in items)
    gk = t.player_profile(player_id="home-00")["results"]["home"][0]["rating"]
    assert gk["value"] is None and gk["reason"] == "saves_not_validated"
    assert "do not cut it" in " ".join(t.player_profile(from_t_s=3.0)["limitations"])


def test_high_press_candidate_end_to_end(tmp_path):
    # away-02 carries at (25, 0) in the home attacking third; home-03 presses from 4 m (pressure 0.2) or 1 m (0.8) in alternating 5 s windows while the home block rises
    d = [4.0, 1.0] * 3
    shifts = [0.0, 20.0, 0.0, 30.0, 0.0, 40.0]
    over = lambda i: {"away-02": (25.0, 0.0), "home-03": (25.0 - d[i // 50], 0.0)}
    rows = make_rows(300, owner_of=lambda i: "away-02", shift_of=lambda i: shifts[i // 50], over=over)
    dd, t = package(tmp_path / "hp", rows, [tackle(270, "home", "home-03", 30.0, "away-02")])
    cands = [json.loads(l) for l in open(os.path.join(dd, "interpret", "phases.jsonl"))]
    hp = [c for c in cands if c["phase"] == "high_press"]
    assert len(hp) == 1 and hp[0]["team"] == "home" and hp[0]["from_t_s"] == 25.0 and hp[0]["evidence"]["event_indices"] == [0] and hp[0]["values"]["high_regains"] == 1
    assert [c["candidate_id"] for c in cands] == list(range(len(cands)))
    r = t.pressing_profile(team="home", metrics=["high_press", "pressure"])["results"]["home"]
    assert r["high_press"]["count"] == 3 and r["pressure"]["band"] is not None and r["high_press"]["pressure_q75"] == pytest.approx(0.8)


def test_phases_file_empty_when_no_candidates(tmp_path):
    out = os.path.join(str(tmp_path), "interpret", "phases.jsonl")
    path = tmp_path
    write(path, "meta.json", {"match_id": "m", "source": {"camera_setup": "synthetic"}, "pitch": {"length_m": 108.8, "width_m": 70.2}, "video": {"fps": 10, "frames": 40}})
    write(path, "roster.json", {"players": [{"player_id": p["player_id"], "team": p["player_id"][:4], "name": "n", "number": 1, "role": p["role"]} for p in static_row(0)["players"]]})
    write(path, "tracking.jsonl", [static_row(i) for i in range(40)])
    write(path, "events.jsonl", [])
    analyze(str(path))
    assert os.path.exists(out) and os.path.getsize(out) == 0


# ---- review fixes ------------------------------------------------------------------------------------------------------------------------------------------------------------

def test_loose_rows_and_mixed_phases(tmp_path):  # review #2, #3
    t = package(tmp_path / "loose", make_rows(300, owner_of=lambda i: None if 20 <= i < 60 else "away-03", shift_of=varied))[1]
    r = t.team_shape(team="home", metrics=["block_height"])
    assert r["sample"]["loose_s"] == pytest.approx(4.0)
    bh = r["results"]["home"]["block_height"]  # no in_possession: no single phase, no band, no percentile
    assert bh["value"] is not None and bh["band"] is None and bh["percentile"] is None and bh["relative_reason"] == "mixed_phases" and r["sufficient_evidence"] is False
    opp = t.team_shape(team="home", metrics=["block_height"], in_possession=False)["sample"]
    assert opp["opponent_owned_s"] == pytest.approx(25.9)  # loose time is not defending


def test_window_s_does_not_change_references(long_match):  # review #4
    a = long_match.team_shape(team="home", in_possession=False, metrics=["block_height"], until_t_s=4.0)
    b = long_match.team_shape(team="home", in_possession=False, metrics=["block_height"], until_t_s=4.0, window_s=1.0)
    assert a["results"] == b["results"] and b["results"]["home"]["block_height"]["n_windows"] == 6
    assert any("ignored" in x for x in b["limitations"]) and b["thresholds_used"]["reference_window_s"] == 5.0


def test_time_is_integrated_by_intersection(long_match):  # review #9
    tiny = long_match.match_context(team="home", from_t_s=1.05, until_t_s=1.15)
    assert tiny["sample"]["eligible_s"] == pytest.approx(0.1)
    a = long_match.match_context(team="home", until_t_s=2.05)["sample"]["eligible_s"]
    b = long_match.match_context(team="home", from_t_s=2.05, until_t_s=4.0)["sample"]["eligible_s"]
    assert a + b == pytest.approx(long_match.match_context(team="home", until_t_s=4.0)["sample"]["eligible_s"]) == pytest.approx(4.0)


def test_episodes_by_overlap_and_unclassified(tmp_path):  # review #10, #11
    d, t = package(tmp_path / "lb", make_rows(300, shift_of=lambda i: [0.0, 0.0, 30.0, 30.0, 30.0, 30.0][i // 50]))
    r = t.team_shape(team="home", from_t_s=2.0, until_t_s=4.0, in_possession=False, metrics=["block_band"])["results"]["home"]["block_band"]
    ep = r["low_block_candidates"]
    assert len(ep) == 1 and ep[0]["from_t_s"] == 0.0 and ep[0]["until_t_s"] == 9.9 and ep[0]["covered_s"] == pytest.approx(2.0)
    pa = t.possession_analysis(team="home", from_t_s=2.0, until_t_s=4.0, metrics=["phase_candidates"])["results"]["home"]["phase_candidates"]
    assert pa["count"] == 1 and pa["items"][0]["phase"] == "low_block" and pa["items"][0]["covered_s"] == pytest.approx(2.0) and pa["unclassified_s"] == pytest.approx(0.0)
    out = t.possession_analysis(team="home", from_t_s=12.0, until_t_s=14.0, metrics=["phase_candidates"])["results"]["home"]["phase_candidates"]
    assert out["count"] == 0 and out["unclassified_s"] == pytest.approx(2.0)


def scored_match(tmp_path):
    rows = make_rows(200)
    for r in rows[100:]:
        r["score"] = {"home": 1, "away": 0}
    return package(tmp_path / "score", rows)[1]


def test_score_state_applies_to_sequences_and_effective_time_is_per_team(tmp_path):  # review #12, #13
    t = scored_match(tmp_path)
    lead = t.tactical_evidence(team="home", score_state="leading", kind="sequences")
    assert all(s["start_t_s"] >= 10.0 for s in lead["results"]["all"]["sequences"]["items"])
    trail = t.tactical_evidence(team="home", score_state="trailing", kind="sequences")
    assert trail["results"]["all"]["sequences"]["total"] == 0 and trail["sufficient_evidence"] is False
    c = t.match_context(score_state="trailing")["results"]["match"]["effective_time_s"]
    assert c["home"] == 0.0 and c["away"] == pytest.approx(10.0, abs=0.2)
    assert isinstance(t.match_context(score_state="all")["results"]["match"]["effective_time_s"], float)


def test_compare_partial_and_zero_denominator(long_match):  # review #14, #15
    z = long_match.compare_metrics(["pressure"], "home", {"until_t_s": 4.0}, {"from_t_s": 15.0, "until_t_s": 19.0})["results"]["home"]["pressure"]
    assert z["diff"] == 0.0 and z["ratio"] is None and z["pct_change"] is None and z["reason"] == "zero_reference_denominator" and z["ratio_reason"] == "zero_reference_denominator"
    fake = lambda value, reason: {"until_t_s": 1.0, "sufficient_evidence": True, "limitations": [], "thresholds_used": {}, "sample": {}, "evidence": {"event_indices": [], "sequence_ids": [], "timeline_windows": [], "frame_ranges": []},
                                  "results": {"home": {"xg": {"value": value, "reason": reason, "shots": 2, "shots_with_xg": 1 if reason else 2}}}}
    vals = iter([fake(0.3, "some_shots_without_xg"), fake(0.5, None)])
    long_match.match_context = lambda **kw: next(vals)
    x = long_match.compare_metrics(["xg"], "home", {})
    r = x["results"]["home"]["xg"]
    assert r["partial"] is True and r["a"]["reason"] == "some_shots_without_xg" and r["a"]["coverage"] == {"shots": 2, "shots_with_xg": 1} and r["reason"].startswith("partial_inputs")
    assert r["diff"] == -0.2 and x["sufficient_evidence"] is False
