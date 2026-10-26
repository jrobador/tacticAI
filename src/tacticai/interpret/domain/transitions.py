"""Pure possession analysis over sequences: possessions, build-up, transitions and counters. A gain is a sequence that opens right after the other team's sequence
ended `lost`, by a recovery or a loose ball (kick-offs and set pieces are restarts, and the first sequence of a clip proves no earlier recovery).
Every record carries from_t_s / until_t_s, event_indices (indices into events_enriched) and frame_range."""
from .frame import x_att

TRANSITION_S, COUNTER_GAIN_M = 5.0, 20.0


def _events_in(events, f0, f1):
    return [j for j, e in enumerate(events) if f0 <= e["frame_index"] <= f1]


def gains(seqs):
    return [k for k, s in enumerate(seqs) if k and seqs[k - 1]["team"] != s["team"] and seqs[k - 1]["end_cause"] == "lost" and s["start_cause"] in ("recovery", "loose_ball")]


def _transition(rows, idx, seqs, events, k, length, transition_s):
    """The first transition_s of gaining sequence k, from its team's point of view."""
    s = seqs[k]
    i0, i1 = idx[s["start_frame"]], idx[s["end_frame"]]
    ids = [i for i in range(i0, i1 + 1) if rows[i]["t_s"] - rows[i0]["t_s"] <= transition_s + 1e-9]
    xs = [x_att(rows[i]["ball"]["x"], s["team"]) for i in ids]
    f0, f1 = rows[ids[0]]["frame_index"], rows[ids[-1]]["frame_index"]
    ev = _events_in(events, f0, f1)
    return {"sequence_id": k, "start_cause": s["start_cause"], "from_t_s": rows[ids[0]]["t_s"], "until_t_s": rows[ids[-1]]["t_s"], "start_xa": xs[0], "gain_m": max(xs) - xs[0],
            "reached_final_third": max(xs) >= length / 6, "shots": sum(events[j]["type"] == "shot" and events[j]["team"] == s["team"] for j in ev),
            "event_indices": ev, "frame_range": [f0, f1]}


def attacking_transitions(rows, idx, seqs, events, team, length, transition_s=TRANSITION_S):
    return [_transition(rows, idx, seqs, events, k, length, transition_s) for k in gains(seqs) if seqs[k]["team"] == team]


def defensive_transitions(rows, idx, seqs, events, team, length, transition_s=TRANSITION_S):
    """The first transition_s after `team` lost the ball: what the rival did with it and whether the team regained it within that time."""
    out = []
    for k in gains(seqs):
        if seqs[k]["team"] == team:
            continue
        t = _transition(rows, idx, seqs, events, k, length, transition_s)
        back = seqs[k + 1]["start_t_s"] - t["from_t_s"] if k + 1 < len(seqs) and seqs[k + 1]["team"] == team and seqs[k]["end_cause"] == "lost" else None
        out.append({"sequence_id": k - 1, "opponent_sequence_id": k, "from_t_s": t["from_t_s"], "until_t_s": t["until_t_s"], "opponent_gain_m": t["gain_m"],
                    "opponent_reached_final_third": t["reached_final_third"], "shots_conceded": t["shots"],
                    "regained": back is not None and back <= transition_s + 1e-9, "regained_after_s": back if back is not None and back <= transition_s + 1e-9 else None,
                    "event_indices": t["event_indices"], "frame_range": t["frame_range"]})
    return out


def counters(rows, idx, seqs, events, team, length, transition_s=TRANSITION_S, gain_m=COUNTER_GAIN_M):
    """Attacking transitions that start with a recovery at start_xa < L/6, advance >= gain_m and reach the final third or a shot."""
    return [t for t in attacking_transitions(rows, idx, seqs, events, team, length, transition_s)
            if t["start_cause"] == "recovery" and t["start_xa"] < length / 6 and t["gain_m"] >= gain_m and (t["reached_final_third"] or t["shots"])]


def build_ups(rows, idx, seqs, events, team, length):
    """Build-up episodes of `team` anywhere inside its possession (sequence): each maximal run of rows with the ball in its own third (x_att < -L/6), until the ball leaves that
    third, the team loses it or play stops. A possession can hold several (it can go back to the own third); no minimum duration."""
    out = []
    for s in seqs:
        if s["team"] != team:
            continue
        i0, i1 = idx[s["start_frame"]], idx[s["end_frame"]]
        inside = lambda i: x_att(rows[i]["ball"]["x"], team) < -length / 6
        i = i0
        while i <= i1:
            if not inside(i):
                i += 1
                continue
            j = i
            while j < i1 and inside(j + 1):
                j += 1
            exited = j < i1
            end = j + 1 if exited else j
            f0, f1 = rows[i]["frame_index"], rows[end]["frame_index"]
            out.append({"sequence_id": s["sequence_id"], "from_t_s": rows[i]["t_s"], "until_t_s": rows[end]["t_s"], "duration_s": rows[end]["t_s"] - rows[i]["t_s"],
                        "outcome": "exited_third" if exited else "lost" if s["end_cause"] == "lost" else "interrupted",
                        "event_indices": _events_in(events, f0, f1), "frame_range": [f0, f1]})
            i = end + 1
    return out


def possession_summary(seqs):
    """Aggregate of the team's sequences (None fields when there are none)."""
    n = len(seqs)
    causes = {}
    for s in seqs:
        causes[s["end_cause"]] = causes.get(s["end_cause"], 0) + 1
    return {"n": n, "mean_duration_s": sum(s["duration_s"] for s in seqs) / n if n else None, "mean_passes": sum(s["passes"] for s in seqs) / n if n else None,
            "max_x_att": max((s["max_x_att"] for s in seqs), default=None), "lines_broken": sum(s["lines_broken"] for s in seqs), "end_causes": causes,
            "sequence_ids": [s["sequence_id"] for s in seqs]}
