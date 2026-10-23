"""Pure possession sequences (contract interpret/sequences.jsonl) from open-play rows, ingest events and the stable owners (pressure.owners_for).
A sequence is a maximal stretch of open-play rows owned by one team; ownerless rows keep the current sequence. A shot by the other team (raw last touch) splits it. It ends on an owner-team change, a set piece or other
stoppage (game_state leaves open_play, or a frame_index gap), a score change or a period change. Rows outside open play belong to no sequence."""
from bisect import bisect_right

from ...ingest.domain.contract import team_of
from ...ingest.domain.events import DEFAULTS, infer_owner, is_break
from .frame import opponent, release_index, x_att
from .lines import lines_broken
from .physical import is_open

RECOVERY_S = 0.5
TOUCH_S = 2.0


def _recovery(events, team, t):
    return any(abs(e["t_s"] - t) <= RECOVERY_S and (e["type"] == "tackle" and e["team"] == team
                                                    or e["type"] == "pass" and e["outcome"] == "intercepted" and team_of(e["intercepted_by"]) == team)
               for e in events)


def _touched(rows, i, team):
    """True if `team` has a raw touch (infer_owner) within TOUCH_S up to row i."""
    return any((o := infer_owner(r, DEFAULTS["owner_radius_m"], DEFAULTS["owner_max_z_m"])) and o[0] == team
               for r in rows[:i + 1] if r["t_s"] >= rows[i]["t_s"] - TOUCH_S)


def _spans(rows, events, owners):
    """[{team, i0, i1, players, start_cause, why, after, goal, at}] with why in lost | stop | score | period | eod (rows i0..i1 inclusive); goal: the score rose for the span's team
    at row `at`. A shot by the other team splits the sequence (the shooter's one starts at the shot row); a score for the opponent with a raw touch in the last TOUCH_S
    is credited to a one-row sequence of the scorer (own goals without a touch keep the old sequence, end `out`)."""
    out, cur, pending, seen, prev_score = [], None, None, set(), None
    idx = {r["frame_index"]: i for i, r in enumerate(rows)}
    shots = {idx[e["frame_index"]]: e for e in events if e["type"] == "shot" and e["frame_index"] in idx}

    def close(why, after=None, at=None):
        nonlocal cur, prev_score
        t, last = cur["team"], rows[cur["i1"]]
        out.append({**cur, "why": why, "after": after, "at": at, "goal": why == "score" and after[t] > last["score"][t]})
        cur, prev_score = None, last["score"]

    for i, r in enumerate(rows):
        p, lost, o = rows[i - 1] if i else None, False, owners[i]
        if p:
            why = ("period" if r["period"] != p["period"] else "score" if r["score"] != p["score"]
                   else "stop" if r["frame_index"] - p["frame_index"] > 1 or is_break(p, r) else None)
            if why:
                t = opponent(cur["team"]) if cur else None
                if cur and why == "score" and r["score"][t] > p["score"][t] and _touched(rows, i, t):  # ponytail: touch by position only
                    close("lost")
                    out.append({"team": t, "i0": i, "i1": i, "players": [], "start_cause": "loose_ball", "why": "score", "after": r["score"], "at": r["frame_index"], "goal": True})
                    pending = None
                    continue
                if cur:
                    close(why, r["score"], r["frame_index"] if why == "score" else None)
                pending = None
        if not is_open(r):
            pending = r["game_state"] if r["game_state"] != "open_play" else pending
            continue
        if cur and i in shots and shots[i]["team"] != cur["team"]:  # one-touch shot by the opponent: the stable owner never changes
            t = shots[i]["team"]
            cur["i1"] = cur.get("own", cur["i0"])
            close("lost")
            cur = {"team": t, "i0": i, "i1": i, "players": [shots[i]["player_id"]], "start_cause": "recovery" if _recovery(events, t, r["t_s"]) else "loose_ball"}
            seen.add(r["period"])
            o = None
        if cur and o and o[0] != cur["team"]:
            close("lost")
            lost = True
        if cur is None and o:
            t = o[0]
            sc = ("kick_off" if r["period"] not in seen or pending == "kick_off" or prev_score is not None and r["score"] != prev_score
                  else f"set_piece:{pending}" if pending else "recovery" if lost and _recovery(events, t, r["t_s"]) else "loose_ball")
            cur, pending = {"team": t, "i0": i, "players": [], "start_cause": sc}, None
            seen.add(r["period"])
        if cur:
            cur["i1"] = i
            if o and o[0] == cur["team"]:
                cur["own"] = i
            if o and o[1] not in cur["players"]:
                cur["players"].append(o[1])
    if cur:
        close("eod")
    return out


def sequences(rows, events, owners):
    """-> (sequences, event_sequence_ids). Sequence fields as in the contract; xg is None until shots are scored. event_sequence_ids is aligned with events:
    the sequence whose [start_frame, end_frame] holds the event frame, or None; an intercepted pass goes to the passer's sequence (its frame opens the interceptor's)."""
    spans = _spans(rows, events, owners)
    starts = [rows[s["i0"]]["frame_index"] for s in spans]
    ends = [rows[s["i1"]]["frame_index"] for s in spans]

    def seq_of(e):
        f, k = e["frame_index"], bisect_right(starts, e["frame_index"]) - 1
        if k > 0 and e["type"] == "pass" and f == starts[k] and spans[k]["team"] != e["team"] == spans[k - 1]["team"]:
            return k - 1
        return k if k >= 0 and f <= ends[k] else None

    goal_seq = {(s["at"], s["team"]): k for k, s in enumerate(spans) if s["goal"]}
    ids = [goal_seq.get((e["frame_index"], e["team"])) if e["type"] == "goal" else seq_of(e) for e in events]
    idx, out = {r["frame_index"]: i for i, r in enumerate(rows)}, []
    for k, s in enumerate(spans):
        t, r0, r1 = s["team"], rows[s["i0"]], rows[s["i1"]]
        mine = [e for e, j in zip(events, ids) if j == k and e["team"] == t]
        passes = [e for e in mine if e["type"] == "pass"]
        goal = s["goal"]
        shot = any(e["type"] == "shot" for e in mine) and s["why"] in ("lost", "stop")
        end = ("goal" if goal else "out" if s["why"] == "score" else "shot" if shot else "lost" if s["why"] == "lost"
               else "out" if s["why"] == "stop" else "end_of_period")
        out.append({"sequence_id": k, "team": t, "start_t_s": r0["t_s"], "end_t_s": r1["t_s"], "start_frame": starts[k], "end_frame": ends[k],
                    "start_clock_s": r0["clock_s"], "period": r0["period"], "start_cause": s["start_cause"], "end_cause": end,
                    "passes": len(passes), "duration_s": r1["t_s"] - r0["t_s"], "start_x_att": x_att(r0["ball"]["x"], t),
                    "max_x_att": max(x_att(r["ball"]["x"], t) for r in rows[s["i0"]:s["i1"] + 1]),
                    "lines_broken": sum(lines_broken(e, rows[release_index(rows, owners, e, idx)]) for e in passes), "xg": None, "goal": goal, "players": s["players"]})
    return out, ids
