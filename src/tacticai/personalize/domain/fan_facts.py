"""Fan facts: everything a supporter lives in a match, detected by code from the analysis. The Supporter agent only writes them.

A supporter reacts to every play, so nothing is filtered out: every pass, carry, tackle, shot, lost ball and goal is a fact, with all
the data that colours it (lines broken, metres gained, how hard and from where it was struck, the run into a tackle...). On top of them
come the facts that span plays (a passing move, who is on top, the game turning, the longest sprints), the verdict, ratings and awards.
Big facts (goals, shots, punished mistakes) are "moments" (the video holds on them); the rest are "reactions" (a live feed).

The words that qualify a fact come from the data, not from a hand-picked constant:
- a clear chance is a shot the xG model rates above the scoring rate of its own test shots (better than the average shot);
- a mistake is a lost pass; it was punished when the rival scored before the team touched the ball again;
- "pinned back" is a run of windows whose possession share is one standard deviation above the match mean;
- a turn is a momentum swing larger than the match's own momentum spread;
- player ratings are bands of the match's VAEP distribution, with a goal or an assist lifting the band;
- a passing move ("olé") is a team's longest spell of completed passes when the xPass model gave it less than an even chance of surviving
  (the product of its passes' xPass is below one half: the move was more likely to break down than not);
- a pass splits the block when it breaks two of the rival's three lines (midfield and defence);
- a shooter is alone when no defender stands between the ball and the goal (the analysis' defenders_in_cone);
- the run into a tackle is the tackler's own run over the RUN_S seconds before it, from the tracking;
- a sprint is the analysis' own (speed above the match's sprint threshold for at least sprint_min_s); each side's longest one is a fact;
- the full-time awards are the match leaders of the analysis (distance, top speed, sprints, completed passes, hardest shot).
Numbers reach the agent only as placeholders ({minute}, {home_goals}...), like everywhere else in the pipeline."""
import json
import os
from statistics import mean, pstdev

FACTS_VERSION = 2
_MODELS = os.path.join(os.path.dirname(__file__), "..", "..", "interpret", "models")
#: Box depth on a football pitch (Laws of the Game), used to say "from outside the box".
BOX_M = 16.5
#: Six-yard box depth, used to say "from close range".
SIX_YARD_M = 5.5
#: Consecutive open-play windows a side must dominate to be "pinned back" (a sixth of the timeline's windows).
PINNED_SHARE_OF_WINDOWS = 1 / 6
#: Lines of a team's block (defence, midfield, attack); a pass breaking two of them has split the block.
SPLIT_BLOCK_LINES = 2
#: Seconds a fan card stays on the video (the UI reads it from the view).
CARD_S = 6.0
#: The run into a tackle: the tackler's movement over the seconds before he wins the ball (a pressing run lasts about this long).
RUN_S = 2.0
KMH = 3.6
#: Kinds the video holds on; every other fact is a reaction in the live feed.
MOMENT_KINDS = ("goal", "save", "miss")


def clear_chance_xg():
    """The scoring rate of the xG model's own test shots: a shot rated above it is better than the average shot."""
    with open(os.path.join(_MODELS, "xg_v1.json"), encoding="utf-8") as f:
        test = json.load(f)["metrics"]["test"]
    return test["goals"] / test["n"]


def _other(s):
    return "away" if s == "home" else "home"


def _minute(clock_s):
    return int(clock_s // 60) + 1


def _count(v):
    return {"value": v, "unit": "count"}


def _build_up(goal, events):
    """The shot that scored and the completed pass to the shooter in the 10 s before it (the assist), if any."""
    shot = next((e for e in reversed(events) if e["type"] == "shot" and e["team"] == goal["team"] and e["t_s"] <= goal["t_s"]), None)
    assist = shot and next((e for e in reversed(events) if e["type"] == "pass" and e["team"] == goal["team"] and e.get("outcome") == "complete"
                            and e.get("to_player_id") == shot["player_id"] and e["t_s"] <= shot["t_s"] and shot["t_s"] - e["t_s"] < 10), None)
    return shot, assist


def _where(shot):
    d = shot and shot.get("dist_goal_center_m")
    return None if d is None else "outside_box" if d > BOX_M else "close_range" if d < SIX_YARD_M else "in_the_box"


def _strike(shot):
    """How hard the ball was hit, when the analysis measured it."""
    v = shot and shot.get("ball_speed_m_s")
    return {"shot_kmh": _count(round(v * KMH))} if v else {}


def _goal_fact(g, events, seqs):
    s, before = g["team"], g["score_before"]
    shot, assist = _build_up(g, events)
    after = {**before, s: before[s] + 1}
    margin = before[s] - before[_other(s)]
    # The first goal of the match also puts that side ahead, so it carries both claims.
    claims = ["first_goal", "go_ahead"] if before["home"] + before["away"] == 0 else ["equaliser"] if margin == -1 else ["go_ahead"] if margin == 0 else []
    situation = "opener" if "first_goal" in claims else "equaliser" if claims == ["equaliser"] else "go_ahead" if claims == ["go_ahead"] else "pulls_one_back" if margin < -1 else "extends_lead"
    seq = seqs.get(g.get("sequence_id"))
    move = {"move_passes": _count(seq["passes"]), "move_players": _count(len(seq["players"]))} if seq and seq["passes"] >= 2 else {}
    return {"kind": "goal", "t_s": g["t_s"], "team": s, "claims": claims, "situation": situation, "where": _where(shot),
            **({"from_own_half": seq["start_x_att"] < 0} if move else {}),
            "players": {"scorer": g.get("scorer_id") or g["player_id"], **({"assist": assist["player_id"]} if assist else {})},
            "metrics": {"minute": _count(_minute(g["clock_s"])), "home_goals": _count(after["home"]), "away_goals": _count(after["away"]), **move, **_strike(shot)}}


def _fed_by(e, events):
    """The completed pass to e's player in the 10 s before e, if any."""
    return next((p for p in reversed(events) if p["type"] == "pass" and p["team"] == e["team"] and p.get("outcome") == "complete"
                 and p.get("to_player_id") == e["player_id"] and p["t_s"] <= e["t_s"] and e["t_s"] - p["t_s"] < 10), None)


def _shot_fact(e, clear_xg, keepers, events):
    """Every shot that did not score: kept out by the keeper (on target) or off target, with all that colours it."""
    if e.get("outcome") == "goal":
        return None
    s = e["team"]
    keeper = keepers.get(_other(s)) if e.get("on_target") else None
    fed = _fed_by(e, events)
    dist = e.get("dist_goal_center_m")
    return {"kind": "save" if e.get("on_target") else "miss", "t_s": e["t_s"], "team": s, "claims": [], "where": _where(e),
            "clear_chance": (e.get("xg") or 0) > clear_xg, **({"alone": e["defenders_in_cone"] == 0} if e.get("defenders_in_cone") is not None else {}),
            "players": {"shooter": e["player_id"], **({"passer": fed["player_id"]} if fed else {}), **({"keeper": keeper} if keeper else {})},
            "metrics": {"minute": _count(_minute(e["clock_s"])), **_strike(e), **({"shot_m": _count(round(dist))} if dist is not None else {})}}


def _mistake_fact(e, events):
    """Every lost pass; punished when the rival scored before the passer's team touched the ball again, `threat` when they shot."""
    if e["type"] != "pass" or e.get("outcome") != "intercepted":
        return None
    s, scored, shot = e["team"], False, False
    for x in events:
        if x["t_s"] <= e["t_s"]:
            continue
        if x["team"] == s and x["type"] != "goal":
            break  # the ball came back
        if x["team"] == _other(s) and x["type"] in ("shot", "goal"):
            shot = True
            if x["type"] == "goal" or x.get("outcome") == "goal":
                scored = True
                break
    return {"kind": "mistake", "t_s": e["t_s"], "team": s, "claims": [], "punished": scored, "threat": shot,
            "players": {"culprit": e["player_id"], **({"winner": e["intercepted_by"]} if e.get("intercepted_by") else {})},
            "metrics": {"minute": _count(_minute(e["clock_s"]))}}


def _pass_fact(e):
    """Every completed pass, with the lines it broke and the ground it gained."""
    if e["type"] != "pass" or e.get("outcome") != "complete":
        return None
    lines, gain = e.get("lines_broken") or 0, e.get("progressive_m") or 0
    return {"kind": "pass", "t_s": e["t_s"], "team": e["team"], "claims": [], "splits_block": lines >= SPLIT_BLOCK_LINES,
            **({"risky": e["xpass"] < 0.5} if e.get("xpass") is not None else {}),  # the xPass model gave it less than an even chance
            "players": {"passer": e["player_id"], **({"receiver": e["to_player_id"]} if e.get("to_player_id") else {})},
            "metrics": {"minute": _count(_minute(e["clock_s"])), **({"lines_broken": {"value": lines, "unit": "lines"}} if lines else {}),
                        **({"gain_m": _count(round(gain))} if gain >= 1 else {}), **({"pass_m": _count(round(e["length_m"]))} if e.get("length_m") else {})}}


def _run(track, pid, t0, t1):
    """(metres, top km/h) of a player between t0 and t1, from the tracking ({player_id: [(t, x, y, speed)]})."""
    pts = [p for p in track.get(pid, []) if t0 <= p[0] <= t1]
    if len(pts) < 2:
        return None, None
    return sum(((b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:])), max(p[3] for p in pts) * KMH


def _carry_fact(e, track):
    if e["type"] != "carry":
        return None
    _, top = _run(track, e["player_id"], e["t_s"], e["t_s"] + e["duration_s"])
    return {"kind": "carry", "t_s": e["t_s"], "team": e["team"], "claims": [], "players": {"carrier": e["player_id"]},
            "metrics": {"minute": _count(_minute(e["clock_s"])), "carry_m": _count(round(e["distance_m"])), **({"carry_kmh": _count(round(top))} if top else {})}}


def _tackle_fact(e, track):
    """Every ball won with a tackle, with the tackler's run into it."""
    if e["type"] != "tackle":
        return None
    dist, top = _run(track, e["player_id"], e["t_s"] - RUN_S, e["t_s"])
    return {"kind": "tackle", "t_s": e["t_s"], "team": e["team"], "claims": [],
            "players": {"winner": e["player_id"], **({"loser": e["from_player_id"]} if e.get("from_player_id") else {})},
            "metrics": {"minute": _count(_minute(e["clock_s"])), **({"run_m": _count(round(dist)), "run_kmh": _count(round(top))} if dist else {})}}


def _flow_facts(timeline):
    out = []
    shares = [w["home"]["possession_share"] for w in timeline if w["home"]["possession_share"] is not None]
    if len(shares) >= 3:
        mu, sd = mean(shares), pstdev(shares)
        need = max(2, round(len(timeline) * PINNED_SHARE_OF_WINDOWS))
        i, last = 0, None
        while i < len(timeline):
            sh = timeline[i]["home"]["possession_share"]
            side = None if sh is None or sd == 0 else "home" if sh >= mu + sd else "away" if sh <= mu - sd else None
            n = 1
            while side and i + n < len(timeline):
                q = timeline[i + n]["home"]["possession_share"]
                if q is None or (side == "home" and q < mu + sd) or (side == "away" and q > mu - sd):
                    break
                n += 1
            if side and n >= need and side != last:
                w = timeline[i]
                out.append({"kind": "pinned", "t_s": w["start_t_s"], "team": side, "claims": [], "players": {},
                            "metrics": {"minute": _count(_minute(w["start_clock_s"]))}})
                last = side
            i += n
    mom = [w["momentum"] for w in timeline]
    spread = pstdev(mom) if len(mom) >= 3 else 0
    for a, b in zip(timeline, timeline[1:]):
        if spread and abs(b["momentum"] - a["momentum"]) > 2 * spread and (a["momentum"] < 0) != (b["momentum"] < 0):
            side = "home" if b["momentum"] > 0 else "away"
            out.append({"kind": "turn", "t_s": b["start_t_s"], "team": side, "claims": [], "players": {},
                        "metrics": {"minute": _count(_minute(b["start_clock_s"]))}})
    return out


def _move_facts(sequences, events, goal_seqs):
    """Each side's longest spell of completed passes, when the xPass model gave it less than an even chance (a move that scored lives in its goal)."""
    out = []
    for side in ("home", "away"):
        spells = []
        for q in sequences:
            if q["team"] == side and q["sequence_id"] not in goal_seqs:
                done = [e for e in events if e.get("sequence_id") == q["sequence_id"] and e["type"] == "pass" and e.get("outcome") == "complete"]
                if done and all(e.get("xpass") is not None for e in done):
                    spells.append((q, done))
        if not spells:
            continue
        q, done = max(spells, key=lambda s: len(s[1]))
        survive = 1.0
        for e in done:
            survive *= e["xpass"]
        if survive >= 0.5:
            continue
        t = done[-1]
        out.append({"kind": "move", "t_s": t["t_s"], "team": side, "claims": [], "players": {},
                    "metrics": {"minute": _count(_minute(t["clock_s"])), "passes": _count(len(done)), "players_in_move": _count(len(q["players"]))}})
    return out


def _sprint_facts(sprints, team_of):
    """Each side's longest sprint of the match (`sprints` carry clock_s next to t_s)."""
    out = []
    for side in ("home", "away"):
        best = max((r for r in sprints if team_of.get(r["player_id"]) == side), key=lambda r: r["distance_m"], default=None)
        if best:
            out.append({"kind": "sprint", "t_s": best["t_s"], "team": side, "claims": [], "players": {"runner": best["player_id"]},
                        "metrics": {"minute": _count(_minute(best["clock_s"])), "run_m": _count(round(best["distance_m"])),
                                    "top_kmh": _count(round(best["top_speed_m_s"] * KMH))}})
    return out


#: Full-time awards: (award, metric, value of an interpret/players.json record or None).
AWARDS = [
    ("engine", "distance_m", lambda p: round(p["physical"]["distance_m"])),
    ("fastest", "top_kmh", lambda p: round(p["physical"]["top_speed_m_s"] * KMH)),
    ("sprinter", "sprints", lambda p: p["physical"]["sprints"]),
    ("playmaker", "passes_completed", lambda p: p["passing"]["completed"]),
    ("rocket", "shot_kmh", lambda p: p["shooting"]["max_shot_speed_m_s"] and round(p["shooting"]["max_shot_speed_m_s"] * KMH)),
]


def _awards(players):
    out = []
    for award, metric, get in AWARDS:
        vals = [(get(p), p) for p in players if get(p)]
        if vals:
            v, p = max(vals, key=lambda x: x[0])
            out.append({"award": award, "player_id": p["player_id"], "team": p["team"], "claims": [], "metrics": {metric: _count(v)}})
    return out


def _ratings(events, roster, goals):
    """Per player: the VAEP of his actions, a band from the match's own VAEP distribution (a goal or an assist lifts it) and his counts."""
    acting = {p["player_id"]: p for p in roster if any(e.get("player_id") == p["player_id"] for e in events if e["type"] != "goal")}
    scorers = [g["players"]["scorer"] for g in goals]
    assists = [g["players"].get("assist") for g in goals]
    vaep = {pid: sum((e.get("vaep") or {}).get("total", 0) for e in events if e.get("player_id") == pid) for pid in acting}
    ranked = sorted(vaep.values())
    def pct(v):
        return sum(1 for x in ranked if x <= v) / len(ranked) if ranked else 0
    out = []
    for pid, p in acting.items():
        mine = [e for e in events if e.get("player_id") == pid]
        passes = [e for e in mine if e["type"] == "pass"]
        done = sum(1 for e in passes if e.get("outcome") == "complete")
        q = pct(vaep[pid])
        band = 3 if pid in scorers or q >= 0.9 else 2 if pid in assists or (vaep[pid] > 0 and q >= 0.5) else 0 if vaep[pid] < 0 and q <= 0.25 else 1
        claims = sorted({c for g in goals if g["players"]["scorer"] == pid for c in g["claims"]})  # a scorer may call his goal what it was
        out.append({"player_id": pid, "team": p["team"], "band": band, "vaep": round(vaep[pid], 3), "claims": claims,
                    "metrics": {"goals": _count(scorers.count(pid)), "assists": _count(assists.count(pid)), "shots": _count(sum(1 for e in mine if e["type"] == "shot")),
                                "passes": _count(len(passes)), "passes_completed": _count(done), "passes_lost": _count(len(passes) - done),
                                "tackles": _count(sum(1 for e in mine if e["type"] == "tackle"))}})
    return sorted(out, key=lambda r: (-r["band"], -r["vaep"]))


def _track(rows):
    """{player_id: [(t_s, x, y, speed m/s)]} from tracking rows."""
    out = {}
    for r in rows:
        for p in r["players"]:
            out.setdefault(p["player_id"], []).append((r["t_s"], p["x"], p["y"], ((p.get("vx") or 0) ** 2 + (p.get("vy") or 0) ** 2) ** 0.5))
    return out


def detect(events, timeline, roster, sequences=(), sprints=(), players=(), rows=()):
    """-> {"facts_version", "clear_chance_xg", "card_s", "facts": [...], "verdict": {...}, "ratings": [...], "awards": [...]}, facts in time
    order with ids f00, f01... and a `tier` ("moment" or "reaction"). `sequences` = interpret/sequences.jsonl, `sprints` = physical.sprint_runs,
    `players` = interpret/players.json records, `rows` = tracking.jsonl (all optional)."""
    clear_xg = clear_chance_xg()
    keepers = {p["team"]: p["player_id"] for p in roster if p.get("role") == "GK"}
    seqs = {q["sequence_id"]: q for q in sequences}
    track = _track(rows)
    team_of = {p["player_id"]: p["team"] for p in roster}
    goal_seqs = {g.get("sequence_id") for g in events if g["type"] == "goal"}
    goals = [_goal_fact(g, events, seqs) for g in events if g["type"] == "goal"]
    plays = [f for e in events for f in (_shot_fact(e, clear_xg, keepers, events) if e["type"] == "shot" else None, _mistake_fact(e, events),
                                         _pass_fact(e), _carry_fact(e, track), _tackle_fact(e, track)) if f]
    facts = goals + plays + _flow_facts(timeline) + _move_facts(list(sequences), events, goal_seqs) + _sprint_facts(sprints, team_of)
    facts.sort(key=lambda f: f["t_s"])
    for i, f in enumerate(facts):
        f["fact_id"] = f"f{i:02d}"
        f["tier"] = "moment" if f["kind"] in MOMENT_KINDS or (f["kind"] == "mistake" and f["punished"]) else "reaction"
    score = {s: sum(1 for g in goals if g["team"] == s) for s in ("home", "away")}
    chances = {s: sum(1 for e in events if e["type"] == "shot" and e["team"] == s and (e.get("outcome") == "goal" or (e.get("xg") or 0) > clear_xg)) for s in ("home", "away")}
    winner = "home" if score["home"] > score["away"] else "away" if score["away"] > score["home"] else None
    ratings = _ratings(events, roster, goals)
    figure = ratings[0]["player_id"] if ratings and ratings[0]["band"] >= 2 else None
    verdict = {"winner": winner, "deserved": None if winner is None else chances[winner] >= chances[_other(winner)],
               "figure": figure, "claims": [],
               "metrics": {"home_goals": _count(score["home"]), "away_goals": _count(score["away"]),
                           "home_chances": _count(chances["home"]), "away_chances": _count(chances["away"]),
                           **{f"{s}_passes": _count(sum(1 for e in events if e["type"] == "pass" and e["team"] == s)) for s in ("home", "away")},
                           **{f"{s}_sprints": _count(sum(p["physical"]["sprints"] for p in players if p["team"] == s)) for s in ("home", "away") if players}}}
    return {"facts_version": FACTS_VERSION, "clear_chance_xg": round(clear_xg, 3), "card_s": CARD_S, "facts": facts, "verdict": verdict, "ratings": ratings,
            "awards": _awards(players)}
