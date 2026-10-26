"""Moment detectors and per-note adapters. Pure functions over what Interpret publishes; nothing is recomputed from tracking.
A candidate is an insight without insight_id, importance and text, plus the internal fields `strength` and `score_before` (consumed by importance.py and dropped by build_insights).
`metrics` are always scalars {"value", "unit"}; `refs` are identifiers to go back to the data and are never cited."""
from . import claims as C

MOMENTUM_REVIEWED = False  # momentum insights stay off until the notes are checked against a video


def _m(value, unit):
    return {"value": value, "unit": unit}


def _opp(team):
    return "away" if team == "home" else "home"


def score_at(events, t_s):
    """score_before of the last event with event.t_s <= t_s (0-0 if none)."""
    last = None
    for e in events:
        if e["t_s"] <= t_s:
            last = e
    return dict(last["score_before"]) if last else {"home": 0, "away": 0}


def _base(kind, subtype, note, i, players, metrics, events):
    return {"kind": kind, "subtype": subtype, "team": note["team"], "players": players, "t_s": note["t_s"], "until_t_s": note["until_t_s"], "show_t_s": note["until_t_s"],
            "clock_s": note["start_clock_s"], "period": note["period"], "metrics": metrics,
            "refs": {"note_index": i, "sequence_ids": [], "event_indices": [], "candidate_id": None}, "claims": [],
            "strength": note["strength"], "score_before": score_at(events, note["t_s"])}


def lines_broken_insight(note, i, sequences, events):
    ev = note["evidence"]
    seq = next((s for s in sequences if s["sequence_id"] == ev["sequence_ids"][0]), None)
    metrics = {"lines_broken": _m(ev["lines_broken"], "lines"), "passes": _m(ev["passes"], "passes"), "duration_s": _m(ev["duration_s"], "s")}
    if ev.get("xg"):
        metrics["xg"] = _m(round(ev["xg"], 3), "engine xG")
    out = _base("lines_broken", ev["end_cause"], note, i, list(seq["players"]) if seq else [], metrics, events)
    out["refs"]["sequence_ids"] = list(ev["sequence_ids"])
    if ev["end_cause"] == "goal":  # the play is shown at the goal, which can land after the note closes
        gi = next((j for j, e in enumerate(events) if e["type"] == "goal" and e.get("sequence_id") == ev["sequence_ids"][0]), None)
        if gi is not None:
            out["until_t_s"] = out["show_t_s"] = max(note["until_t_s"], events[gi]["t_s"])
            out["refs"]["event_indices"] = [gi]
    return out


def pressure_insight(note, i, events):
    ev = note["evidence"]
    if note["kind"] == "pressure_peak":
        sub, metrics = "peak", {"value": _m(ev["value"], "0-1"), "match_mean": _m(ev["match_mean"], "0-1")}
    else:
        sub, metrics = ("shift_up" if note["text_key"] == "pressure_up" else "shift_down"), {"before": _m(ev["before"], "0-1"), "after": _m(ev["after"], "0-1")}
    out = _base("pressure_spell", sub, note, i, [], metrics, events)
    out["claims"] = C.pressure_claims(sub)
    return out


def momentum_insight(note, i, events):
    """Adapter kept working while the detector is gated (MOMENTUM_REVIEWED)."""
    ev, team = note["evidence"], note["team"]
    if note["kind"] == "momentum_swing":
        sub = "swing"
        metrics = {"before": _m(ev.get("mean_before", ev["values"][0]), "momentum"), "after": _m(ev.get("mean_after", ev["values"][-1]), "momentum")}
    else:
        sub = "dominance"
        metrics = {"mean_momentum": _m(ev["mean_momentum"], "momentum"), "xg": _m(ev["xg"][team], "engine xG"), "final_third_entries": _m(ev["final_third_entries"][team], "entries")}
    return _base("momentum_shift", sub, note, i, [], metrics, events)


def associated_shot(events, gi):
    """Index of the last shot of the goal's team with outcome goal, the same (non-null) sequence_id and t_s before the goal; None if there is none."""
    g = events[gi]
    if g.get("sequence_id") is None:
        return None
    hits = [j for j, e in enumerate(events) if e["type"] == "shot" and e["team"] == g["team"] and e.get("outcome") == "goal" and e.get("sequence_id") == g["sequence_id"] and e["t_s"] < g["t_s"]]
    return hits[-1] if hits else None


def goal_insight(events, gi, notes):
    g = events[gi]
    si = associated_shot(events, gi)
    shot = events[si] if si is not None else None
    metrics = {"xg": _m(round(shot["xg"], 3), "engine xG")} if shot and shot.get("xg") is not None else {}
    absorbed = next((n for n, note in enumerate(notes) if si is not None and note["kind"] == "big_chance" and si in note["evidence"]["event_indices"]), None)
    first = shot or g
    before = dict(g["score_before"])
    return {"kind": "goal_or_chance", "subtype": "goal", "team": g["team"], "players": [g["scorer_id"]], "t_s": first["t_s"], "until_t_s": g["t_s"], "show_t_s": g["t_s"],
            "clock_s": first["clock_s"], "period": g["period"], "metrics": metrics,
            "refs": {"note_index": absorbed, "sequence_ids": [g["sequence_id"]] if g.get("sequence_id") is not None else [],
                     "event_indices": [si, gi] if si is not None else [gi], "candidate_id": None},
            "claims": C.goal_claims(g["team"], before), "strength": 1.0, "score_before": before}


def chance_insight(note, i, events):
    ev = note["evidence"]
    out = _base("goal_or_chance", "chance_scored" if note["text_key"] == "big_chance_scored" else "chance_missed", note, i, [ev["player_id"]], {"xg": _m(round(ev["xg"], 3), "engine xG")}, events)
    out["refs"]["event_indices"] = list(ev["event_indices"])
    return out


def detect(notes, sequences, events):
    """All candidates of a match, unordered. Notes are indexed by their line in tactical_notes.jsonl (note_index)."""
    out = [goal_insight(events, gi, notes) for gi, e in enumerate(events) if e["type"] == "goal"]
    absorbed = {c["refs"]["note_index"] for c in out}
    for i, n in enumerate(notes):
        k = n["kind"]
        if k == "line_breaking_sequence":
            out.append(lines_broken_insight(n, i, sequences, events))
        elif k in ("pressure_shift", "pressure_peak"):
            out.append(pressure_insight(n, i, events))
        elif k == "big_chance" and i not in absorbed:
            out.append(chance_insight(n, i, events))
        elif k in ("momentum_swing", "dominance_spell") and MOMENTUM_REVIEWED:
            out.append(momentum_insight(n, i, events))
    return out


def with_agent_context(cands, agents, phases):
    """Adds `agent_context` (and refs.candidate_id) from interpret/agents.json `tactical`; agents may be None. Without it every insight gets []."""
    tac = (agents or {}).get("tactical") or {}
    keys = {k["note_index"]: k for k in tac.get("key_notes", [])}
    ph = {p["candidate_id"]: p for p in phases or []}
    for c in cands:
        ctx = []
        k = keys.get(c["refs"]["note_index"]) if c["refs"]["note_index"] is not None else None
        if k:
            ctx.append({"ref": "key_note", "note_index": k["note_index"], "rank": k["rank"], "text": k["text"]})
        hits = [a for a in tac.get("phases", []) if a["candidate_id"] in ph and ph[a["candidate_id"]]["team"] == c["team"]
                and ph[a["candidate_id"]]["from_t_s"] <= c["until_t_s"] and c["t_s"] <= ph[a["candidate_id"]]["until_t_s"]]
        if hits:
            a = min(hits, key=lambda a: a["rank"])
            ctx.append({"ref": "phase", "candidate_id": a["candidate_id"], "rank": a["rank"], "text": a["text"]})
            c["refs"]["candidate_id"] = a["candidate_id"]
        c["agent_context"] = ctx
    return cands
