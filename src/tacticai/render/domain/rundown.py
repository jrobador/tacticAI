"""Broadcast rundown: the timed, machine-readable graphics a broadcast graphics engine draws over the live feed (render/broadcast/rundown.json).
Pure code from the analysis, no agent: every graphic is a fact with its numbers, so it can go on air with no human approval.

Graphics, in the two slots of an L-bar (as broadcasters' data zones do):
- bar (along the bottom): goal, shot (ball speed, distance, xG), pass quality on every completed pass that breaks a line (distance,
  completion chance from the xPass model, and how hard it was compared with the match's other passes), carry (metres, top speed);
- side (the right column, under the minimap): player identification when a player first crosses the match's sprint threshold
  (name, top speed, distance covered so far), and milestones when a player reaches a count set in advance (MILESTONES).
A graphic is on air from t_in to t_out (video seconds); each slot shows one graphic at a time, the latest that is on air."""

RUNDOWN_VERSION = 1
KMH = 3.6
#: Seconds a graphic stays on air; a goal's lower-third is shorter: the full-screen takeover at net_t carries the moment.
ON_AIR_S, GOAL_ON_AIR_S = 5.0, 4.0
#: Milestones the broadcaster sets before the match: (event, counts that fire a graphic). The usual practice of data zones
#: ("a player reaches 5 interceptions"), kept here as configuration rather than spread through the code.
MILESTONES = {"tackle": (2, 3, 5), "shot": (2, 3, 5), "pass": (5, 10, 20, 40)}


def _g(kind, slot, t, e, data, hold=ON_AIR_S):
    return {"type": kind, "slot": slot, "t_in": round(t, 2), "t_out": round(t + hold, 2), "clock_s": e.get("clock_s"), "team": e.get("team"),
            "player_id": e.get("player_id"), "data": data}


def _assist(shot, events):
    """The passer of the last completed pass by the scorer's team to the scorer in the 10 s before the shot, else None."""
    p = next((p for p in reversed(events) if p["type"] == "pass" and p["team"] == shot["team"] and p.get("outcome") == "complete"
              and p.get("to_player_id") == shot["player_id"] and p["t_s"] <= shot["t_s"] and shot["t_s"] - p["t_s"] < 10), None)
    return p["player_id"] if p else None


def _bar(events, xpass_all, net_t):
    out = []
    for e in events:
        t = e["type"]
        if t == "goal":
            mine = [s for s in reversed(events) if s["type"] == "shot" and s["team"] == e["team"] and s["t_s"] <= e["t_s"]]
            shot = next((s for s in mine if s.get("outcome") == "goal"), mine[0] if mine else None)
            after = {**e["score_before"], e["team"]: e["score_before"][e["team"]] + 1}
            out.append(_g("goal", "bar", e["t_s"], {**e, "player_id": e.get("scorer_id") or e["player_id"]},
                          {"score": after, **({"ball_kmh": round(shot["ball_speed_m_s"] * KMH)} if shot and shot.get("ball_speed_m_s") else {}),
                           **({"distance_m": round(shot["dist_goal_center_m"], 1)} if shot and shot.get("dist_goal_center_m") is not None else {}),
                           **({"net_t": net_t(shot["t_s"])} if shot and net_t else {}), "assist_player_id": shot and _assist(shot, events)}, GOAL_ON_AIR_S))
        elif t == "shot" and e.get("outcome") != "goal":
            out.append(_g("shot", "bar", e["t_s"], e, {"ball_kmh": e.get("ball_speed_m_s") and round(e["ball_speed_m_s"] * KMH),
                                                       "distance_m": e.get("dist_goal_center_m") and round(e["dist_goal_center_m"], 1),
                                                       "xg": e.get("xg") and round(e["xg"], 2), "on_target": bool(e.get("on_target"))}))
        elif t == "pass" and e.get("outcome") == "complete" and (e.get("lines_broken") or 0) >= 1:
            xp = e.get("xpass")
            harder = None if xp is None or not xpass_all else round(100 * sum(1 for x in xpass_all if x > xp) / len(xpass_all))
            out.append(_g("pass_quality", "bar", e["t_s"], e, {"to_player_id": e.get("to_player_id"), "length_m": e.get("length_m") and round(e["length_m"], 1),
                                                               "lines_broken": e["lines_broken"], "completion_pct": None if xp is None else round(100 * xp),
                                                               "harder_than_pct": harder}))
        elif t == "carry":
            out.append(_g("carry", "bar", e["t_s"], e, {"distance_m": round(e["distance_m"], 1), "duration_s": e["duration_s"]}))
    return out


def _side(events, sprints, travelled):
    out, seen = [], set()
    for s in sorted(sprints, key=lambda s: s["t_s"]):
        if s["player_id"] in seen:
            continue
        seen.add(s["player_id"])
        out.append(_g("player_id", "side", s["t_s"], {"clock_s": s.get("clock_s"), "team": s["team"], "player_id": s["player_id"]},
                      {"top_kmh": round(s["top_speed_m_s"] * KMH, 1), "distance_m": round(travelled(s["player_id"], s["t_s"]))}))
    counts = {}
    for e in events:
        kind = "pass" if e["type"] == "pass" and e.get("outcome") == "complete" else e["type"]
        if kind not in MILESTONES or not e.get("player_id"):
            continue
        n = counts[(e["player_id"], kind)] = counts.get((e["player_id"], kind), 0) + 1
        if n in MILESTONES[kind]:
            out.append(_g("milestone", "side", e["t_s"], e, {"event": kind, "count": n}))
    return out


def build(events, sprints, travelled, match_id, net_t=None):
    """events = interpret/events_enriched.jsonl; sprints = physical.sprint_runs with team and clock_s; travelled(player_id, t) -> metres
    covered up to t; net_t(shot t_s) -> video second the ball reaches the net (goal takeover). -> the rundown: graphics in time order with ids g000, g001..."""
    xpass_all = [e["xpass"] for e in events if e["type"] == "pass" and e.get("xpass") is not None]
    graphics = sorted(_bar(events, xpass_all, net_t) + _side(events, sprints, travelled), key=lambda g: (g["t_in"], g["slot"]))
    for i, g in enumerate(graphics):
        g["id"] = f"g{i:03d}"
    return {"rundown_version": RUNDOWN_VERSION, "match_id": match_id, "clock": "video seconds (t_in, t_out); clock_s is the match clock",
            "slots": {"bar": "along the bottom of the L-bar", "side": "right column of the L-bar, under the minimap"},
            "milestones": {k: list(v) for k, v in MILESTONES.items()}, "graphics": graphics}
