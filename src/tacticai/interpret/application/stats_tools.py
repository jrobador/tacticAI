"""Stats Tools: read-only queries over a written analysis package (<match>/interpret/). No metric is recomputed from tracking and no LLM is called.

until_t_s: only records with t_s <= until_t_s count (sequences: end_t_s <= until_t_s, so a sequence still open at that time is not leaked). Aggregates are recomputed from
the filtered events/sequences/timeline. Timeline windows are weighted by their overlap with [0, until_t_s]. FULL-MATCH ONLY (never cut): physical block, rank/percentile,
rating, quality, projection/calibration flags. Every response carries match_id and the until_t_s used; errors are {"error": ..., "valid": [...]}."""
import json
import os

from ..domain.passes import PROGRESSIVE_M

FILES = ("meta.json", "events_enriched.jsonl", "sequences.jsonl", "timeline.jsonl", "players.json", "teams.json", "quality.json")
METRICS = ("lines_broken", "progressive_passes", "xg", "goals", "tackles", "interceptions", "passes", "completion_pct", "rating", "distance_rank", "top_speed_rank")
FULL_ONLY = ["physical", "rating", "quality", "projection", "calibration"]
_cache = {}


def _jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _read(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _round(v, n):
    return None if v is None else round(v, n)


def _ids(root):
    return [m for m in sorted(os.listdir(root)) if os.path.isdir(os.path.join(root, m, "interpret"))] if os.path.isdir(root) else []


def _load(root, match_id):
    d = os.path.join(root, match_id)
    if not os.path.isdir(os.path.join(d, "interpret")):
        return None
    i = lambda f: os.path.join(d, "interpret", f)
    paths = [i(f) for f in FILES] + [os.path.join(d, "meta.json"), os.path.join(d, "roster.json")]
    key = tuple(os.path.getmtime(p) if os.path.exists(p) else None for p in paths)
    hit = _cache.get(d)
    if hit and hit[0] == key:
        return hit[1]
    opt = lambda name, dflt: _read(os.path.join(d, name)) if os.path.exists(os.path.join(d, name)) else dflt
    pkg = {"id": match_id, "meta": _read(i("meta.json")), "events": _jl(i("events_enriched.jsonl")), "sequences": _jl(i("sequences.jsonl")),
           "timeline": _jl(i("timeline.jsonl")), "players": _read(i("players.json"))["players"], "quality": _read(i("quality.json")),
           "match": opt("meta.json", {}), "roster": {p["player_id"]: p for p in opt("roster.json", {"players": []})["players"]}}
    _cache[d] = (key, pkg)
    return pkg


def _err(msg, valid=None, **kw):
    return {"error": msg, **({"valid": valid} if valid is not None else {}), **kw}


def _get(root, match_id):
    pkg = _load(root, match_id)
    return (pkg, None) if pkg else (None, _err(f"unknown match '{match_id}'", _ids(root), match_id=match_id))


def _ok(pkg, until, **kw):
    return {"match_id": pkg["id"], "until_t_s": until, **kw}


def _le(recs, until, key="t_s"):
    return [r for r in recs if until is None or r[key] <= until]


def _team_err(pkg, team, until):
    if team not in ("home", "away"):
        return _err(f"unknown team '{team}'", ["home", "away"], match_id=pkg["id"], until_t_s=until)


def _score(pkg, until):
    s = {"home": 0, "away": 0}
    for e in _le(pkg["events"], until):
        if e["type"] == "goal":
            s[e["team"]] += 1
    return s


def _weights(pkg, until):
    """(window, overlap_s) for windows overlapping [0, until]."""
    out = []
    for w in pkg["timeline"]:
        ov = (w["end_t_s"] if until is None else min(w["end_t_s"], until)) - w["start_t_s"]
        if ov > 0:
            out.append((w, ov))
    return out


def _wmean(pairs, side, field):
    pairs = [(w, o) for w, o in pairs if w[side][field] is not None]  # a window can have no pressure value (team never defended)
    tot = sum(o for _, o in pairs)
    return sum(w[side][field] * o for w, o in pairs) / tot if tot else None


def _stats(pkg, until, who):
    """Counts from events up to until; who(team, player_id) selects the actor (a team or one player)."""
    ev = _le(pkg["events"], until)
    mine = lambda e: who(e["team"], e["player_id"])
    passes = [e for e in ev if e["type"] == "pass" and mine(e)]
    done = [p for p in passes if p["outcome"] == "complete"]
    shots = [e for e in ev if e["type"] == "shot" and mine(e)]
    icpt = lambda e: e["type"] == "pass" and e["intercepted_by"] is not None and who(e["intercepted_by"].split("-")[0], e["intercepted_by"])
    return {"passes": len(passes), "completed": len(done), "completion_pct": round(100 * len(done) / len(passes), 1) if passes else None,
            "progressive_passes": sum(p["progressive_m"] >= PROGRESSIVE_M for p in done), "lines_broken": sum(p["lines_broken"] or 0 for p in done),
            "shots": len(shots), "xg": round(sum(s["xg"] or 0.0 for s in shots), 3), "goals": sum(s["outcome"] == "goal" for s in shots),
            "tackles": sum(e["type"] == "tackle" and mine(e) for e in ev), "interceptions": sum(icpt(e) for e in ev)}


def list_matches(root):
    out = []
    for m in _ids(root):
        pkg = _load(root, m)
        out.append({"match_id": m, "teams": {t: v.get("name") for t, v in pkg["match"].get("teams", {}).items()}, "score": _score(pkg, None),
                    "quality_level": pkg["quality"]["level"]})
    return {"matches": out}


def match_summary(root, match_id, until_t_s=None):
    pkg, e = _get(root, match_id)
    if e:
        return e
    u, pr = until_t_s, _weights(pkg, until_t_s)
    ts = {t: _stats(pkg, u, lambda tm, _p, t=t: tm == t) for t in ("home", "away")}
    return _ok(pkg, u, teams={t: v.get("name") for t, v in pkg["match"].get("teams", {}).items()}, score=_score(pkg, u),
               possession_pct={t: _round(100 * _wmean(pr, t, "possession_share"), 1) if pr else None for t in ("home", "away")},
               xg={t: ts[t]["xg"] for t in ts}, shots={t: ts[t]["shots"] for t in ts}, open_play_s=round(sum(o / (w["end_t_s"] - w["start_t_s"]) for w, o in pr) * pkg["meta"]["thresholds"]["window_open_play_s"], 1),
               quality_level=pkg["quality"]["level"], projection=pkg["meta"]["projection"], calibration=pkg["meta"]["calibration"], full_match_only=FULL_ONLY)


def team_stats(root, match_id, team, until_t_s=None):
    pkg, e = _get(root, match_id)
    if e:
        return e
    if (te := _team_err(pkg, team, until_t_s)):
        return te
    u = until_t_s
    seqs = [s for s in _le(pkg["sequences"], u, "end_t_s") if s["team"] == team]
    return _ok(pkg, u, team=team, **_stats(pkg, u, lambda tm, _p: tm == team), sequences=len(seqs),
               sequences_ending_in_shot=sum(s["end_cause"] in ("shot", "goal") for s in seqs), mean_pressure=_round(_wmean(_weights(pkg, u), team, "pressure"), 3))


def player_stats(root, match_id, player_id, until_t_s=None):
    pkg, e = _get(root, match_id)
    if e:
        return e
    p = next((p for p in pkg["players"] if p["player_id"] == player_id), None)
    if p is None:
        return _err(f"unknown player '{player_id}'", [x["player_id"] for x in pkg["players"]], match_id=pkg["id"], until_t_s=until_t_s)
    r = pkg["roster"].get(player_id, {})
    return _ok(pkg, until_t_s, player_id=player_id, team=p["team"], name=r.get("name"), number=r.get("number"), role=r.get("role"),
               **_stats(pkg, until_t_s, lambda _t, pid: pid == player_id), rating={**p["rating"], "scope": "full_match"},
               physical={**p["physical"], "scope": "full_match", "relative_only": not pkg["meta"]["calibration"]["physical_absolute"]})


def top_players(root, match_id, metric, n=5, until_t_s=None):
    pkg, e = _get(root, match_id)
    if e:
        return e
    if metric not in METRICS:
        return _err(f"unknown metric '{metric}'", list(METRICS), match_id=pkg["id"], until_t_s=until_t_s)
    full = {"rating": lambda p: p["rating"]["value"], "distance_rank": lambda p: p["physical"]["distance_rank"], "top_speed_rank": lambda p: p["physical"]["top_speed_rank"]}
    vals = {p["player_id"]: full[metric](p) if metric in full else _stats(pkg, until_t_s, lambda _t, pid, i=p["player_id"]: pid == i)[metric] for p in pkg["players"]}
    rows = sorted(((k, v) for k, v in vals.items() if v is not None), key=lambda kv: kv[1], reverse=not metric.endswith("_rank"))[:n]  # *_rank: 1 is best
    team = {p["player_id"]: p["team"] for p in pkg["players"]}
    return _ok(pkg, until_t_s, metric=metric, scope="full_match" if metric in full else "until_t_s",
               top=[{"player_id": k, "team": team[k], "name": pkg["roster"].get(k, {}).get("name"), "value": _round(v, 3)} for k, v in rows])


def events(root, match_id, type=None, team=None, player_id=None, from_t_s=None, until_t_s=None, limit=50):
    pkg, e = _get(root, match_id)
    if e:
        return e
    got = [x for x in _le(pkg["events"], until_t_s) if (type is None or x["type"] == type) and (team is None or x["team"] == team)
           and (player_id is None or x["player_id"] == player_id) and (from_t_s is None or x["t_s"] >= from_t_s)]
    return _ok(pkg, until_t_s, from_t_s=from_t_s, total=len(got), events=got[:limit])


def sequences(root, match_id, team=None, end_cause=None, min_lines_broken=None, until_t_s=None, limit=50):
    pkg, e = _get(root, match_id)
    if e:
        return e
    got = [s for s in _le(pkg["sequences"], until_t_s, "end_t_s") if (team is None or s["team"] == team) and (end_cause is None or s["end_cause"] == end_cause)
           and (min_lines_broken is None or s["lines_broken"] >= min_lines_broken)]
    return _ok(pkg, until_t_s, total=len(got), sequences=got[:limit])


def timeline(root, match_id, from_t_s=None, until_t_s=None):
    pkg, e = _get(root, match_id)
    if e:
        return e
    w = [w for w in pkg["timeline"] if (until_t_s is None or w["start_t_s"] <= until_t_s) and (from_t_s is None or w["end_t_s"] >= from_t_s)]
    return _ok(pkg, until_t_s, from_t_s=from_t_s, windows=w)


def shot_map(root, match_id, team=None, until_t_s=None):
    pkg, e = _get(root, match_id)
    if e:
        return e
    keys = ("t_s", "clock_s", "team", "player_id", "x", "y", "end_x", "end_y", "xg", "outcome", "on_target")
    return _ok(pkg, until_t_s, pitch=pkg["match"].get("pitch"),
               shots=[{k: s[k] for k in keys} for s in _le(pkg["events"], until_t_s) if s["type"] == "shot" and (team is None or s["team"] == team)])


def pressure_windows(root, match_id, team, until_t_s=None, top=3):
    pkg, e = _get(root, match_id)
    if e:
        return e
    if (te := _team_err(pkg, team, until_t_s)):
        return te
    w = sorted((w for w, _ in _weights(pkg, until_t_s) if w[team]["pressure"] is not None), key=lambda w: -w[team]["pressure"])[:top]
    keys = ("window", "start_t_s", "end_t_s", "start_clock_s", "end_clock_s", "period")
    return _ok(pkg, until_t_s, team=team, windows=[{**{k: x[k] for k in keys}, "pressure": x[team]["pressure"]} for x in w])


def quality(root, match_id):
    pkg, e = _get(root, match_id)
    return e or {"match_id": pkg["id"], "until_t_s": None, "scope": "full_match", **pkg["quality"]}
