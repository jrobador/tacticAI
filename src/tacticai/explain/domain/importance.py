"""Contextual importance: mean of the available factors, all in 0..1, equal weights, rounded to 3 decimals."""
from .moments import _opp

MATCH_S = 5400.0  # clock_s / MATCH_S, clamped


def team_vaep(events, team, t0, t1):
    """Signed sum of the VAEP attributed to `team` in [t0, t1]: `vaep` to the acting team, `vaep_interception` to the opponent of the passer."""
    s = 0.0
    for e in events:
        if not t0 <= e["t_s"] <= t1:
            continue
        if e["team"] == team and e.get("vaep"):
            s += e["vaep"]["total"]
        if _opp(e["team"]) == team and e.get("vaep_interception"):
            s += e["vaep_interception"]["total"]
    return s


def score_context(score_before):
    return 1.0 if abs(score_before["home"] - score_before["away"]) <= 1 else 0.5


def rate(cands, events, has_vaep):
    """-> [{"value", "factors"}] aligned with `cands` (each with kind, subtype, team, t_s, until_t_s, clock_s, strength, score_before, refs)."""
    sums = [abs(team_vaep(events, c["team"], c["t_s"], c["until_t_s"])) for c in cands] if has_vaep else []
    top = max(sums, default=0.0)
    out = []
    for k, c in enumerate(cands):
        same = [d["strength"] for d in cands if d["kind"] == c["kind"]]
        no_shot = c["kind"] == "goal_or_chance" and c["subtype"] == "goal" and len(c["refs"]["event_indices"]) == 1
        value = None if not has_vaep else 1.0 if no_shot else (sums[k] / top if top > 0 else 0.0)
        f = {"rarity": sum(s <= c["strength"] for s in same) / len(same), "value": value, "score_context": score_context(c["score_before"]),
             "minute": min(1.0, max(0.0, c["clock_s"] / MATCH_S))}
        vals = [v for v in f.values() if v is not None]
        out.append({"value": round(sum(vals) / len(vals), 3), "factors": {n: None if v is None else round(v, 3) for n, v in f.items()}})
    return out
