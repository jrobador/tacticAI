"""Pure player rating (contract: 6.0 + documented points per action, always with its breakdown; goalkeepers get no value until saves are validated)."""
RATING_WEIGHTS = {"lines_broken": 0.1, "progressive_passes": 0.1, "xg": 1.0, "goals_minus_xg": 1.0, "tackles": 0.2, "interceptions": 0.2, "losses_own_half": -0.2}
BASE, LOW, HIGH = 6.0, 1.0, 10.0


def rating(p):
    """p: flat dict with role, lines_broken, progressive_passes, xg (None without a model), goals, tackles, interceptions, losses_own_half.
    -> {"value", "breakdown": [{"item", "count" | "value", "points"}], "reason"}; zero-point items are omitted."""
    if p["role"] == "GK":
        return {"value": None, "breakdown": [], "reason": "saves_not_validated"}
    items = [(k, "count", p[k]) for k in ("lines_broken", "progressive_passes")]
    if p["xg"] is not None:
        items += [("xg", "value", p["xg"]), ("goals_minus_xg", "value", p["goals"] - p["xg"])]
    items += [(k, "count", p[k]) for k in ("tackles", "interceptions", "losses_own_half")]
    bd = [{"item": k, kind: v, "points": round(RATING_WEIGHTS[k] * v, 2)} for k, kind, v in items if RATING_WEIGHTS[k] * v]
    value = BASE + sum(RATING_WEIGHTS[k] * v for k, _, v in items)
    return {"value": round(min(HIGH, max(LOW, value)), 1), "breakdown": bd, "reason": None}
