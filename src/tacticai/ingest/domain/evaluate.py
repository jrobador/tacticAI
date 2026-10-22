"""Pure evaluation of a generated match/situation against a recipe's `wanted` predicates."""
from . import metrics

LATE_S = 4800


def _goals(events):
    return [e for e in events if e["type"] == "goal"]


def _met(pred, events, roster):
    name, _, arg = pred.partition(":")
    goals = _goals(events)
    if name == "ends_in_shot":
        return any(e["type"] in ("shot", "goal") for e in events)
    if name == "ends_in_goal":
        return bool(goals)
    if name == "goal_by_team":
        return any(e["team"] == arg for e in goals)
    if name == "goal_by":
        names = {p["player_id"]: p["name"].lower() for p in roster["players"]}
        return any(e["scorer_id"] is not None and names[e["scorer_id"]] == arg.lower() for e in goals)
    return True  # ranking predicates are not pass/fail


def meets(wanted, events, roster):
    """(ok, missing): AND over the boolean predicates; more_pressure/more_possession only rank."""
    missing = [p for p in wanted if not _met(p, events, roster)]
    return not missing, missing


def rank_value(wanted, rows, events):
    """Sum of the ranking predicates: recoveries in the opponent half per min and possession share."""
    v = 0.0
    for p in wanted:
        name, _, arg = p.partition(":")
        if name == "more_pressure":
            v += metrics.recoveries_opp_half_per_min(rows, events, arg) or 0
        elif name == "more_possession":
            v += (metrics.possession_pct(rows, arg) or 0) / 100
    return v


def interest_score(events):
    """(score, reasons) for a full match: goals*3, comeback +5, late goals +3 each, lead changes +2 each, shots*0.2.
    A lead change is a new leader different from the previous leader (a draw in between still counts).
    ponytail: momentum (swings in possession/pressure) is not implemented."""
    score, trailed, leader, changes, late = [0, 0], [False, False], None, 0, 0
    goals = sorted((e for e in events if e["type"] == "goal"), key=lambda e: e["clock_s"])
    for g in goals:
        score[g["team"] == "away"] += 1
        late += g["clock_s"] >= LATE_S
        trailed = [t or score[i] < score[1 - i] for i, t in enumerate(trailed)]
        if score[0] != score[1]:
            lead = int(score[1] > score[0])
            changes += leader is not None and lead != leader
            leader = lead
    comeback = any(trailed[i] and score[i] >= score[1 - i] for i in (0, 1))
    shots = sum(e["type"] == "shot" for e in events)
    total = 3 * len(goals) + 5 * comeback + 3 * late + 2 * changes + 0.2 * shots
    return total, {"goals": len(goals), "comeback": comeback, "late_goals": late, "lead_changes": changes, "shots": shots}


def evaluate(recipe, rows, events, roster):
    """{"ok", "missing", "score", "reasons"} for one generated run."""
    wanted = recipe.situation.wanted if recipe.situation else []
    ok, missing = meets(wanted, events, roster)
    score, reasons = rank_value(wanted, rows, events), {}
    if recipe.mode == "full_match":
        extra, reasons = interest_score(events)
        score += extra
    return {"ok": ok, "missing": missing, "score": score, "reasons": reasons}
