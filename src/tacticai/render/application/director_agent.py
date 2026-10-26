"""Director Agent: one Foundry call per match plans the overlays of the 12 combinations {analyst, fan, first_match, broadcast} x {neutral, home, away}.
plans.py validates each plan; NotImplementedError (no FOUNDRY_*), any error or an invalid plan means the rules plan is used."""
import json

from pydantic import BaseModel

from ...agents import foundry
from ..domain import director as D

INSTRUCTIONS = """You are the director of the on-screen overlays of a football broadcast. You receive the key moments (insights) of one match as JSON and 12 plans to make, one per `combo` (lens x club). For EACH combo choose which moments to show, in which slot and for how long.

Each combo gives:
- `threshold`: the minimum priority an insight should have to be shown. Use it as guidance: you may pick an insight below it only if you justify it in `reason`.
- `slots`: the places on screen. Each overlay occupies its slot from the insight's `show_t_s` until `show_t_s + duration_s`. Two overlays of the same slot must never overlap in time; overlays of different slots may. An empty slots list (broadcast) is a queue: use slot null and no overlap check applies.
- `min_duration_s` and `max_duration_s`: the allowed duration of an overlay.
- `rules_plan`: the plan a simple rule-based director would make. It is valid, use it as a reference and improve it for the audience when you can.

Audiences:
- analyst: three slots; show the richest, most informative moments, a dense screen is fine.
- fan: one slot; only the big emotional moments (goals, chances, strong swings), never crowd the screen.
- first_match: one slot; few and easy moments, with enough time to read.
- broadcast: a queue without slots; the moments worth a graphic for a TV audience.
- Club: for `home` or `away` the viewer follows that club (My Club). Each insight has a `priority` per club (importance plus a bonus for that club's own insights): prefer the insights of that club, and keep its moments when they compete with the rival's. `neutral` is even-handed.

Rules:
- Use only insight ids from the input, each at most once per plan. Do not choose show times: they come from the insight.
- Longer durations for goals (about eight seconds), shorter for the rest (about six); stay inside the allowed range.
- Do not return an empty plan: if nothing reaches the threshold, show the best moments you can justify in `reason`.
- `reason`: one short sentence saying why this moment is shown for this audience. Describe the football, not the numbers.
- Answer every combo exactly once, with the same `combo` key."""


class Overlay(BaseModel):
    insight_id: str
    slot: str | None
    duration_s: float
    reason: str


class Plan(BaseModel):
    combo: str
    overlays: list[Overlay]


class Out(BaseModel):
    plans: list[Plan]


def _compact(d, teams):
    return {"insight_id": d["insight_id"], "kind": d["kind"], "subtype": d["subtype"], "team": teams.get(d["team"], {}).get("name", d["team"]), "side": d["team"],
            "show_t_s": d["show_t_s"], "claims": d["claims"], "importance": d["importance"]["value"], "default_duration_s": D.duration(d),
            "priority": {club: D.priority(d, club) for club in ("neutral", "home", "away")}}


def plan_all(insights, rules_by_combo, match_context):
    """rules_by_combo {"<lens>_<club>": {"threshold", "slots", "min_duration_s", "max_duration_s", "rules_plan"}} -> {"<lens>_<club>": [{"insight_id", "slot", "duration_s", "reason"}]}.
    One call per match. Without FOUNDRY_* raises NotImplementedError: every plan uses the rules. Other errors propagate. show_t_s is not chosen by the agent."""
    if not foundry.configured():
        raise NotImplementedError("Foundry not configured")
    teams = match_context.get("teams", {})
    combos = [{"combo": k, **r} for k, r in rules_by_combo.items()]
    msg = json.dumps({"insights": [_compact(d, teams) for d in insights], "combos": combos}, ensure_ascii=False)
    out = foundry.run(INSTRUCTIONS, msg, response_format=Out, timeout_s=60)
    return {p.combo: [o.model_dump() for o in p.overlays] for p in out.plans}
