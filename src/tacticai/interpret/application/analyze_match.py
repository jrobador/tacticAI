"""Analyze one match package (contract section 1) and write <match_dir>/interpret/ (contract section 2): the 7 deterministic files plus tactical_notes.jsonl (deterministic candidate notes).
xg_model / xpass_model: optional callables f(feature_dict) -> probability (shot kick-candidate features / pass_features); None leaves the dependent fields null."""
import os

from ...ingest.domain.events import DEFAULTS
from ...ingest.infrastructure.files import read_json, read_jsonl, write_json, write_jsonl
from ..domain import physical
from ..domain.frame import opponent, release_index, third, x_att
from ..domain.lines import lines_broken
from ..domain.passes import pass_features, pass_stats
from ..domain.patterns import tactical_notes
from ..domain.pressure import RADIUS_M, owners_for, pressing_events, pressure_on, team_pressure
from ..domain.quality import quality
from ..domain.rating import RATING_WEIGHTS, rating
from ..domain.sequences import sequences
from ..domain.shots import kick_candidates
from ..domain.timeline import MOMENTUM_WEIGHTS, N_WINDOWS, timeline

MATCH_WINDOW_S = 3  # a shot event matches the kick candidate of the same team within +-3 frames (as the ingest label)


def _count(name, n, mins, meta):
    rate = n / mins if mins else None
    return {name: n, f"{name}_per_min": rate, f"{name}_projected": physical.project(rate, meta)}


def _model_info(m):
    return None if m is None else getattr(m, "info", {"id": getattr(m, "__name__", "custom")})


def _enrich(rows, owners, events, meta, roster, th, xg_model, xpass_model):
    """-> (enriched events, sequences, {event index: xg})."""
    idx = {r["frame_index"]: i for i, r in enumerate(rows)}
    length = meta["pitch"]["length_m"]
    seqs, seq_ids = sequences(rows, events, owners)
    ps = pass_stats(events, rows)["passes"]
    feats = iter(pass_features(rows, owners, events, idx, meta) if xpass_model else [])
    cands = kick_candidates(rows, roster, meta, th, events)
    shot_speeds = iter(physical.ball_speeds(rows, events, meta)["shots"])
    pstats, out, xgs = iter(ps), [], {}
    for j, (e, sid) in enumerate(zip(events, seq_ids)):
        i = idx[e["frame_index"]]
        rel = release_index(rows, owners, e, idx) if e["type"] == "pass" else i
        row = rows[rel]
        rec = {**e, "sequence_id": sid, "pressure": pressure_on(row, e["player_id"]) if e["player_id"] else None,
               "score_before": rows[max(i - 1, 0)]["score"]}
        if e["type"] == "pass":
            s = next(pstats)
            xp = xpass_model(next(feats)) if xpass_model else None
            rec.update(length_m=s["length_m"], progressive_m=s["progressive_m"], lines_broken=lines_broken(e, row), xpass=xp, difficulty=None if xp is None else 1 - xp)
        elif e["type"] == "shot":
            c = min((c for c in cands if c["team"] == e["team"] and abs(c["frame_index"] - e["frame_index"]) <= MATCH_WINDOW_S),
                    key=lambda c: abs(c["frame_index"] - e["frame_index"]), default=None)
            xg = xg_model(c) if xg_model and c else None
            if xg is not None:
                xgs[j] = xg
            rec.update(xg=xg, dist_goal_center_m=c and c["dist_goal_center_m"], visible_goal_angle_deg=c and c["visible_goal_angle_deg"],
                       defenders_in_cone=c and c["defenders_in_cone"], ball_speed_m_s=next(shot_speeds)["ball_speed_m_s"], on_target=c and c["on_target_projection"])
        elif e["type"] == "tackle":
            rec["zone"] = third(x_att(e["x"], e["team"]), length)
        out.append(rec)
    for s in seqs:
        s["xg"] = sum(r["xg"] or 0.0 for r in out if r["type"] == "shot" and r["sequence_id"] == s["sequence_id"] and r["team"] == s["team"]) if xg_model else None
    return out, seqs, xgs


def _players(rows, owners, events, enriched, roster, meta, has_xg):
    mins = physical.open_play_seconds(rows) / 60
    phys, thr = physical.player_physical(rows, meta)
    pst = pass_stats(events, rows)["players"]
    pres = pressing_events(rows, owners)
    out = []
    for p in roster["players"]:
        pid, team, foe = p["player_id"], p["team"], opponent(p["team"])
        ph = phys.get(pid)
        mine = [e for e in enriched if e["type"] == "pass" and e["player_id"] == pid]
        shots = [e for e in enriched if e["type"] == "shot" and e["player_id"] == pid]
        diff = [e["difficulty"] for e in mine if e["difficulty"] is not None]
        ps = pst.get(pid, {"passes": 0, "completed": 0, "completion_pct": None, "mean_length_m": None, "passes_per_min": 0.0, "progressive_passes": 0})
        xg = sum(e["xg"] or 0.0 for e in shots) if has_xg else None  # a shot without a matching kick candidate has no xg and adds 0
        tackles = sum(e["type"] == "tackle" and e["player_id"] == pid for e in enriched)
        icpt = sum(e["type"] == "pass" and e["intercepted_by"] == pid for e in enriched)
        lost = (sum(e["outcome"] == "intercepted" and x_att(e["x"], team) < 0 for e in mine)
                + sum(e["type"] == "tackle" and e["from_player_id"] == pid and x_att(e["x"], foe) < 0 for e in enriched))
        lb = sum(e["lines_broken"] for e in mine)
        goals = sum(e["outcome"] == "goal" for e in shots)
        out.append({
            "player_id": pid, "team": team, "minutes_open_play": mins,
            "physical": {k: ph and ph[k] for k in ("distance_m", "distance_per_min", "distance_rank", "distance_percentile", "top_speed_m_s", "top_speed_rank",
                                                   "top_speed_percentile", "sprints", "sprints_per_min", "top_speed_drop_pct")},
            "passing": {**ps, "lines_broken": lb, "mean_difficulty": sum(diff) / len(diff) if diff else None},
            "shooting": {"shots": len(shots), "xg": xg, "goals": goals, "max_shot_speed_m_s": max((e["speed_m_s"] for e in shots), default=None)},
            "defending": {"tackles": tackles, "interceptions": icpt, "pressures": pres.get(pid, 0)},
            "rating": rating({"role": p["role"], "lines_broken": lb, "progressive_passes": ps["progressive_passes"], "xg": xg, "goals": goals,
                              "tackles": tackles, "interceptions": icpt, "losses_own_half": lost}), "_role": p["role"]})
    return out, thr


def _teams(rows, owners, enriched, players, seqs, meta, has_xg):
    mins = physical.open_play_seconds(rows) / 60
    held = [o[0] for r, o in zip(rows, owners) if o and physical.is_open(r)]
    out = []
    for t in ("home", "away"):
        ps = [p for p in players if p["team"] == t and p["_role"] != "GK"]
        sm = lambda blk, k: sum(p[blk][k] or 0 for p in ps)
        n = sm("passing", "passes")
        wavg = lambda blk, k, w: (sum(p[blk][k] * p[blk][w] for p in ps if p[blk][k] is not None) / d) if (d := sum(p[blk][w] for p in ps if p[blk][k] is not None)) else None
        shots = [e for e in enriched if e["type"] == "shot" and e["team"] == t]
        xg = sum(e["xg"] or 0.0 for e in shots) if has_xg else None
        dist = sm("physical", "distance_m")
        mine = [s for s in seqs if s["team"] == t]
        out.append({
            "team": t, "possession_pct": 100 * held.count(t) / len(held) if held else None, "pressure": team_pressure(rows, owners, t), "xg": xg,
            "goals": sum(e["outcome"] == "goal" for e in shots), "sequences": len(mine), "sequences_ending_in_shot": sum(s["end_cause"] in ("shot", "goal") for s in mine),
            "physical": {"distance_m": dist, "distance_per_min": dist / mins if mins else None, "distance_projected": physical.project(dist / mins if mins else None, meta),
                         **_count("sprints", sm("physical", "sprints"), mins, meta),
                         "top_speed_m_s": max((p["physical"]["top_speed_m_s"] for p in ps if p["physical"]["top_speed_m_s"] is not None), default=None)},
            "passing": {**_count("passes", n, mins, meta), **_count("completed", sm("passing", "completed"), mins, meta),
                        "completion_pct": 100 * sm("passing", "completed") / n if n else None, "mean_length_m": wavg("passing", "mean_length_m", "passes"),
                        **_count("progressive_passes", sm("passing", "progressive_passes"), mins, meta), **_count("lines_broken", sm("passing", "lines_broken"), mins, meta),
                        "mean_difficulty": wavg("passing", "mean_difficulty", "passes")},
            "shooting": {**_count("shots", sm("shooting", "shots"), mins, meta), "xg": xg, "goals": sm("shooting", "goals"),
                         "max_shot_speed_m_s": max((p["shooting"]["max_shot_speed_m_s"] for p in ps if p["shooting"]["max_shot_speed_m_s"] is not None), default=None)},
            "defending": {**_count("tackles", sm("defending", "tackles"), mins, meta), **_count("interceptions", sm("defending", "interceptions"), mins, meta),
                          **_count("pressures", sm("defending", "pressures"), mins, meta)}})
    return out


def analyze(match_dir, xg_model=None, xpass_model=None):
    """Reads meta/roster/tracking/events of match_dir, writes <match_dir>/interpret/*; returns the output directory."""
    read = lambda f: os.path.join(match_dir, f)
    meta, roster, rows, events = read_json(read("meta.json")), read_json(read("roster.json")), read_jsonl(read("tracking.jsonl")), read_jsonl(read("events.jsonl"))
    meta = {**meta, "projection": meta.get("projection", physical.DEFAULT_PROJECTION), "calibration": meta.get("calibration", {"physical_absolute": False})}
    meta.setdefault("source", {}).setdefault("camera_setup", "synthetic")
    owners = owners_for(rows)
    enriched, seqs, xgs = _enrich(rows, owners, events, meta, roster, DEFAULTS, xg_model, xpass_model)
    players, thr = _players(rows, owners, events, enriched, roster, meta, xg_model is not None)
    teams = _teams(rows, owners, enriched, players, seqs, meta, xg_model is not None)
    for p in players:
        del p["_role"]
    open_s = physical.open_play_seconds(rows)
    out = os.path.join(match_dir, "interpret")
    os.makedirs(out, exist_ok=True)
    write_json(os.path.join(out, "meta.json"), {
        "analysis_version": 1, "match_id": meta["match_id"], "open_play_s": open_s, "projection": meta["projection"], "calibration": meta["calibration"],
        "models": {"xg": _model_info(xg_model), "xpass": _model_info(xpass_model)},
        "thresholds": {"sprint_speed_m_s": thr, "sprint_min_s": physical.SPRINT_MIN_S, "pressure_radius_m": RADIUS_M, "window_open_play_s": open_s / N_WINDOWS},
        "weights": {"momentum": MOMENTUM_WEIGHTS, "rating": RATING_WEIGHTS}})
    write_jsonl(os.path.join(out, "events_enriched.jsonl"), enriched)
    write_jsonl(os.path.join(out, "sequences.jsonl"), seqs)
    tl = timeline(rows, owners, events, meta, xgs if xg_model else None)
    write_jsonl(os.path.join(out, "timeline.jsonl"), tl)
    write_json(os.path.join(out, "players.json"), {"players": players})
    write_json(os.path.join(out, "teams.json"), {"teams": teams})
    write_json(os.path.join(out, "quality.json"), quality(rows, meta))
    write_jsonl(os.path.join(out, "tactical_notes.jsonl"), tactical_notes(tl, seqs, enriched, meta))
    return out
