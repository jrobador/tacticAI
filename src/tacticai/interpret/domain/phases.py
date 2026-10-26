"""Pure phase candidates: high_press, low_block, build_up, counter. Each comes with its rule, evidence and values; a stretch without candidate is unclassified.
The rules never read the template name. Relative rules (high_press, low_block) need a sufficient match reference (relative.reference) and yield nothing without it.
high_press: high regains inside the interval OR a relatively low PPDA proxy (<= Q25 of the team's PPDA over its complete 5 s defending windows; needs >= MIN_WINDOWS windows with a recovery, non-flat IQR, and
>= PPDA_MIN_RECOVERIES recoveries in the zone inside the interval). Episodes are grouped only inside one continuous rival possession and every piece of evidence lies inside the published interval."""
from bisect import bisect_left

from . import pressure as P, relative as R, shape as S, transitions as T
from .frame import opponent

PPDA_MIN_RECOVERIES = 1


def _ids(seqs, f0, f1, team):
    """Ids of the sequences of `team` overlapping the frame range."""
    return [s["sequence_id"] for s in seqs if s["team"] == team and s["start_frame"] <= f1 and s["end_frame"] >= f0]


def _cand(phase, team, t0, t1, rule, seqs, f0, f1, seq_team, values, extra_events=()):
    ev = sorted(set(extra_events))
    return {"phase": phase, "team": team, "from_t_s": t0, "until_t_s": t1, "rule": rule,
            "evidence": {"event_indices": ev, "sequence_ids": _ids(seqs, f0, f1, seq_team), "frame_ranges": [[f0, f1]]}, "values": values}


def _between(events, t0, t1):
    """[(index, event)] with t0 <= t_s <= t1."""
    return [(j, e) for j, e in enumerate(events) if t0 <= e["t_s"] <= t1]


def _ppda_reference(rows, phs, events, team, length):
    """Reference of the PPDA proxy (rival passes in the zone / own recoveries in the zone) over the team's complete 5 s defending windows that hold at least one recovery."""
    order = sorted(range(len(events)), key=lambda j: events[j]["t_s"])
    ts = [events[j]["t_s"] for j in order]
    st, vals = R.step(rows), []
    for a, b in R.windows(rows, phs, "opp"):
        t0, t1 = rows[a]["t_s"], rows[b]["t_s"] + st
        idx = [(j, events[j]) for j in order[bisect_left(ts, t0):bisect_left(ts, t1 - 1e-9)]]
        n_pass, n_rec = P.ppda_proxy(idx, P.recoveries(idx, team, length), team, length)
        if n_rec:
            vals.append(n_pass / n_rec)
    return R.reference(vals, R.FLAT_IQR_PPDA)


def phase_candidates(rows, owners, events, seqs, meta):
    """-> candidates sorted by from_t_s then team, each with candidate_id = its index."""
    length, idx, out = meta["pitch"]["length_m"], {r["frame_index"]: i for i, r in enumerate(rows)}, []
    for team in ("home", "away"):
        foe = opponent(team)
        for c in T.counters(rows, idx, seqs, events, team, length):
            out.append({"phase": "counter", "team": team, "from_t_s": c["from_t_s"], "until_t_s": c["until_t_s"],
                        "rule": f"recovery at start_xa < L/6, +{T.COUNTER_GAIN_M:g} m in <= {T.TRANSITION_S:g} s, reached final third or shot",
                        "evidence": {"event_indices": c["event_indices"], "sequence_ids": [c["sequence_id"]], "frame_ranges": [c["frame_range"]]},
                        "values": {"gain_m": c["gain_m"], "duration_s": c["until_t_s"] - c["from_t_s"]}})
        for b in T.build_ups(rows, idx, seqs, events, team, length):
            out.append({"phase": "build_up", "team": team, "from_t_s": b["from_t_s"], "until_t_s": b["until_t_s"],
                        "rule": "ball in own third (x_att < -L/6) inside the possession until exit, loss or stoppage",
                        "evidence": {"event_indices": b["event_indices"], "sequence_ids": [b["sequence_id"]], "frame_ranges": [b["frame_range"]]},
                        "values": {"duration_s": b["duration_s"], "outcome": b["outcome"]}})
        phs = R.phases(rows, owners, team)
        bh = {i: m["block_height"] for i, r in enumerate(rows) if (m := S.row_metrics(r, team, length)) and phs[i] == "opp"}
        bh_ref = R.reference(R.window_values(rows, phs, bh, "opp"), R.FLAT_IQR_M)
        if bh_ref["sufficient"]:
            for i0, i1 in S.low_block_episodes(rows, phs, bh, length, bh_ref["q25"]):
                f0, f1 = rows[i0]["frame_index"], rows[i1]["frame_index"]
                out.append(_cand("low_block", team, rows[i0]["t_s"], rows[i1]["t_s"], f"defending in own half with block height below match Q25 for >= {S.LOW_BLOCK_MIN_S:g} s",
                                 seqs, f0, f1, foe, {"block_height_m": sum(bh[i] for i in range(i0, i1 + 1)) / (i1 - i0 + 1), "block_height_q25_m": bh_ref["q25"],
                                                             "duration_s": rows[i1]["t_s"] - rows[i0]["t_s"]}, T._events_in(events, f0, f1)))
        pres = P.pressure_series(rows, owners, team)
        pr_ref = R.reference(R.window_values(rows, phs, pres, "opp"), R.FLAT_IQR_PRESSURE)
        if bh_ref["sufficient"] and pr_ref["sufficient"]:
            eps = P.high_press_episodes(rows, pres, team, length, pr_ref["q75"])
            groups = []
            for e in eps:  # episodes belong to the same spell only inside one continuous rival possession (every row between them 'opp', no gap) less than one window apart
                if groups and (p := groups[-1][-1][1]) is not None and rows[e[0]]["t_s"] - rows[p]["t_s"] <= R.WINDOW_S                         and rows[e[0]]["frame_index"] - rows[p]["frame_index"] == e[0] - p and all(phs[k] == "opp" for k in range(p, e[0] + 1)):
                    groups[-1].append(e)
                else:
                    groups.append([e])
            recs = P.recoveries(list(enumerate(events)), team, length)
            ppda_ref = _ppda_reference(rows, phs, events, team, length)
            st = R.step(rows)
            for g in groups:
                i0, i1 = g[0][0], g[-1][1]
                t0, t1 = rows[i0]["t_s"], rows[i1]["t_s"]
                block = [bh[i] for i in range(i0, i1 + 1) if i in bh]
                if not block or sum(block) / len(block) <= bh_ref["q75"]:
                    continue
                regains = [r["event_index"] for r in recs if r["xa"] >= length / 6 and t0 <= r["t_s"] <= t1]
                inside = _between(events, t0, t1)
                n_pass, n_rec = P.ppda_proxy(inside, [r for r in recs if t0 <= r["t_s"] <= t1], team, length)
                ppda = n_pass / n_rec if n_rec >= PPDA_MIN_RECOVERIES else None
                low_ppda = ppda_ref["sufficient"] and ppda is not None and ppda <= ppda_ref["q25"]
                if regains or low_ppda:
                    why = " and ".join(x for x, ok in (("high regain inside the interval", regains), ("PPDA proxy <= match Q25", low_ppda)) if ok)
                    vals = {"block_height_m": sum(block) / len(block), "block_height_q75_m": bh_ref["q75"], "pressure_q75": pr_ref["q75"],
                            "high_press_s": sum(rows[b]["t_s"] - rows[a]["t_s"] + st for a, b in g), "high_regains": len(regains)}
                    if low_ppda:
                        vals.update(ppda_proxy=ppda, ppda_q25=ppda_ref["q25"])
                    out.append(_cand("high_press", team, t0, t1, "defending in one continuous rival possession; block height above match Q75; high-press episodes (carrier in the attacking third, pressure >= match Q75, "
                                     f">= {P.PRESS_MIN_S:g} s); {why}", seqs, rows[i0]["frame_index"], rows[i1]["frame_index"], foe, vals, regains))
    out.sort(key=lambda c: (c["from_t_s"], c["team"], c["phase"]))
    return [R.rounded({"candidate_id": k, **c}) for k, c in enumerate(out)]
