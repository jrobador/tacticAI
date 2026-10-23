"""Pure deterministic tactical notes (contract interpret/tactical_notes.jsonl): candidate patterns with evidence; no LLM. Every note: t_s, until_t_s, start_clock_s, period, team, kind, text_key,
evidence (never empty), strength in 0..1 (ranks notes later). Same kind + team overlapping in time keep only the strongest. Units: pressure 0..1, momentum -1..1 (home positive), xg probability, seconds."""
from statistics import mean

PRESSURE_SHIFT = 0.15       # |mean pressure of 3 windows - mean of the 3 before| >= this; strength = min(1, diff / 0.5); one note per team per 3 windows
PRESSURE_RUN = 3
PEAK_SCALE = 0.5            # pressure_peak strength = min(1, (peak - match mean) / PEAK_SCALE)
SWING_JUMP = 0.4            # momentum changes sign between consecutive windows with |change| >= this; strength = min(1, jump)
SWING_MIN_NEW = 0.1        # the jump must land at least this far on the new side (not just drift to neutral)
SWING_RUN, SWING_LEVEL = 3, 0.3   # or a 3-window mean flips from >= +level to <= -level (or reverse); strength = |mean_after - mean_before| / 2
SPELL_LEVEL, SPELL_MIN = 0.4, 3   # >= SPELL_MIN consecutive windows with momentum >= +level (home) / <= -level (away); strength = min(1, abs mean momentum)
LINES_MIN = 2               # sequence with lines_broken >= this ending in shot/goal, or the team's top sequence (>= 1); strength = min(1, lines_broken / 5)
BIG_CHANCE_XG = 0.3         # shot with xg >= this; strength = min(1, xg)


def _note(kind, team, text_key, w0, w1, strength, evidence):
    return {"t_s": w0["t_s"], "until_t_s": w1["t_s"], "start_clock_s": w0["clock_s"], "period": w0["period"], "team": team, "kind": kind, "text_key": text_key,
            "evidence": evidence, "strength": round(max(0.0, min(1.0, strength)), 4)}


def _windows(tl, i, j, kind, team, key, strength, ev):
    a, b = tl[i], tl[j]
    return _note(kind, team, key, {"t_s": a["start_t_s"], "clock_s": a["start_clock_s"], "period": a["period"]}, {"t_s": b["end_t_s"]}, strength,
                 {"timeline_windows": [w["window"] for w in tl[i:j + 1]], **ev})


def _pressure_shift(tl):
    out = []
    for t in ("home", "away"):
        p, cand = [w[t]["pressure"] for w in tl], []
        for k in range(PRESSURE_RUN, len(tl) - PRESSURE_RUN + 1):
            b, a = p[k - PRESSURE_RUN:k], p[k:k + PRESSURE_RUN]
            if None in b + a:
                continue
            d = round(mean(a) - mean(b), 9)
            if abs(d) >= PRESSURE_SHIFT:
                cand.append((abs(d), k, mean(b), mean(a), d))
        taken = []
        for _, k, b, a, d in sorted(cand, key=lambda c: (-c[0], c[1])):
            if all(abs(k - k2) >= PRESSURE_RUN for k2 in taken):
                taken.append(k)
                out.append(_windows(tl, k - PRESSURE_RUN, k + PRESSURE_RUN - 1, "pressure_shift", t, "pressure_up" if d > 0 else "pressure_down", abs(d) / 0.5,
                                    {"metric": "pressure", "before": round(b, 3), "after": round(a, 3)}))
    return out


def _pressure_peak(tl):
    out = []
    for t in ("home", "away"):
        ks = [k for k, w in enumerate(tl) if w[t]["pressure"] is not None]
        if ks:
            k = max(ks, key=lambda k: (tl[k][t]["pressure"], -k))
            m = mean(tl[i][t]["pressure"] for i in ks)
            out.append(_windows(tl, k, k, "pressure_peak", t, "highest_pressure_of_match", (tl[k][t]["pressure"] - m) / PEAK_SCALE,
                                {"metric": "pressure", "value": round(tl[k][t]["pressure"], 3), "match_mean": round(m, 3)}))
    return out


def _momentum_swing(tl):
    out, m, n = [], [w["momentum"] for w in tl], SWING_RUN
    for i in range(len(tl) - 1):
        a, b = m[i], m[i + 1]
        if a * b < 0 and round(abs(b - a), 9) >= SWING_JUMP and round(abs(b), 9) >= SWING_MIN_NEW:
            t = "home" if b > 0 else "away"
            out.append(_windows(tl, i, i + 1, "momentum_swing", t, f"momentum_to_{t}", abs(b - a), {"metric": "momentum", "values": [round(a, 3), round(b, 3)]}))
    for i in range(len(tl) - 2 * n + 1):
        a, b = mean(m[i:i + n]), mean(m[i + n:i + 2 * n])
        if a * b < 0 and round(min(abs(a), abs(b)), 9) >= SWING_LEVEL:
            t = "home" if b > 0 else "away"
            out.append(_windows(tl, i, i + 2 * n - 1, "momentum_swing", t, f"momentum_to_{t}", abs(b - a) / 2,
                                {"metric": "momentum", "values": [round(x, 3) for x in m[i:i + 2 * n]], "mean_before": round(a, 3), "mean_after": round(b, 3)}))
    return out


def _dominance_spell(tl):
    out = []
    for t, sign in (("home", 1), ("away", -1)):
        i = 0
        while i < len(tl):
            j = i
            while j < len(tl) and round(sign * tl[j]["momentum"], 9) >= SPELL_LEVEL:
                j += 1
            if j - i >= SPELL_MIN:
                ws, mm = tl[i:j], mean(w["momentum"] for w in tl[i:j])
                out.append(_windows(tl, i, j - 1, "dominance_spell", t, "dominance_spell", abs(mm),
                                    {"mean_momentum": round(mm, 3), "xg": {s: round(sum(w[s]["xg"] for w in ws), 3) for s in ("home", "away")},
                                     "final_third_entries": {s: sum(w[s]["final_third_entries"] for w in ws) for s in ("home", "away")}}))
            i = max(j, i + 1)
    return out


def _line_breaking(seqs):
    pick = {s["sequence_id"]: s for s in seqs if s["lines_broken"] >= LINES_MIN and s["end_cause"] in ("shot", "goal")}
    for t in ("home", "away"):
        mine = [s for s in seqs if s["team"] == t and s["lines_broken"] >= 1]
        if mine:
            top = max(mine, key=lambda s: (s["lines_broken"], -s["sequence_id"]))
            pick[top["sequence_id"]] = top
    return [_note("line_breaking_sequence", s["team"], "line_breaking_move", {"t_s": s["start_t_s"], "clock_s": s["start_clock_s"], "period": s["period"]}, {"t_s": s["end_t_s"]},
                  s["lines_broken"] / 5, {"sequence_ids": [s["sequence_id"]], "lines_broken": s["lines_broken"], "passes": s["passes"], "duration_s": round(s["duration_s"], 2),
                                          "end_cause": s["end_cause"], "xg": s["xg"]}) for s in pick.values()]


def _big_chance(events):
    return [_note("big_chance", e["team"], "big_chance_scored" if e["outcome"] == "goal" else "big_chance_missed", {"t_s": e["t_s"], "clock_s": e["clock_s"], "period": e["period"]},
                  {"t_s": e["t_s"]}, e["xg"], {"event_indices": [j], "frame_index": e["frame_index"], "xg": round(e["xg"], 3), "player_id": e["player_id"]})
            for j, e in enumerate(events) if e["type"] == "shot" and e.get("xg") is not None and e["xg"] >= BIG_CHANCE_XG]


def tactical_notes(timeline, sequences, events, meta):
    """-> notes sorted by t_s. events: enriched events (xg, outcome); meta is accepted for the contract signature (thresholds are module constants)."""
    notes = [n for n in _pressure_shift(timeline) + _pressure_peak(timeline) + _momentum_swing(timeline) + _dominance_spell(timeline) + _line_breaking(sequences) + _big_chance(events)
             if n["evidence"]]
    kept = []
    for n in sorted(notes, key=lambda n: (-n["strength"], n["t_s"])):
        if not any(k["kind"] == n["kind"] and k["team"] == n["team"] and k["t_s"] <= n["until_t_s"] and n["t_s"] <= k["until_t_s"] for k in kept):
            kept.append(n)
    return sorted(kept, key=lambda n: (n["t_s"], n["kind"], n["team"]))
