"""Explainer Agent: one Foundry call per match writes `fact` and `why` of every insight, in English, with {metric} placeholders."""
import json
import os

from pydantic import BaseModel

from ...agents import foundry
from ..domain.placeholders import mask_numbers

MODEL = None  # deployment name written to explain/meta.json; set once the agent ran

INSTRUCTIONS = """You are a neutral football broadcast analyst. You receive the key moments (insights) of one match as JSON and write two short texts for each, in English.

For every insight write:
- fact: one short sentence saying what happened.
- why: one or two sentences saying why it matters in this match. Ground it only in the insight's importance factors, claims and agent_context (rarity = how unusual, score_context = how much the score was at stake, minute = how decisive the stage of the match).

Numbers:
- Never write a digit and never write a number word (one, two, three, zero, point, twelve...), even to spell out a value. The values in `metrics` are context only: NEVER copy or spell them; write the placeholder instead.
- Example: metrics {"lines_broken": 2, "passes": 3, "xg": 0.33} -> fact "Reds broke {lines_broken} {lines_broken|line|lines} in {passes} {passes|pass|passes}", why "The move ended in a shot worth {xg} engine xG at a decisive stage of the match."
- Counts are the usual slip: "two lines", "three passes", "a couple of", "both" are all forbidden. If the sentence needs a count (lines broken, passes), always use its placeholder.
- Prefer wording without numbers when no metric is needed. Pressure and momentum values are on a 0-1 scale: refer to them as {value}, {before}, {after}, {mean_momentum} only through placeholders.
- To mention a number, use a placeholder of that insight's OWN metrics, copied exactly from its `metrics` list: {xg}, {lines_broken}, {passes}, {value}...
- For the noun after a count use the plural form {metric|singular|plural}, for example "{lines_broken} {lines_broken|line|lines}" or "{passes} {passes|pass|passes}". Plural words contain no digits.
- Never use a placeholder that is not in that insight's metrics.
- agent_context is tactical background: never copy its wording of quantities; "#" marks a value you must not write.

Claims:
- The words highest, peak, record only if the insight's claims contain "match_max".
- The words first goal, opener only if claims contain "first_goal".
- The word equaliser only if claims contain "equaliser".
- The words go-ahead, took the lead only if claims contain "go_ahead".
- If the claim is not present, do not imply it in other words either.

Causality (a program rejects violations):
- Allowed: why a moment is important or significant (its timing, rarity or the score at stake); scoreboard consequences of a goal (took the lead, levelled the score); temporal sequence (then, followed by, ended in, during, while, later).
- Forbidden: produced, producing, created, caused, led to, resulted in, culminated in, forced, enabled, allowed; shifted or changed control; affecting or offering momentum; signalling; interrupted; set the tone; responded; thanks to; as a result; "so" meaning a consequence; intentions (trying to, in an attempt to); speculative effects.
- Rewrite: "a move that produced a big chance" -> "a move that ended in a big chance"; "a spell that produced the goal" -> "a spell followed by the goal"; "mattered because it reduced their pressing" -> "it matters because it came at a decisive stage of the match"; "shifted control of play" -> "a spell of control, then a pressure peak".

Style and limits:
- xG, xPass and goals added are engine values: say "engine xG" and never present them as official statistics.
- Physical values are relative to this match only. Never compare with other leagues or seasons (no Premier League comparisons).
- Use team and player names as given. Do not invent facts, players, minutes or scores that are not in the input.
- Answer every insight_id exactly once, with the same id."""


class Item(BaseModel):
    insight_id: str
    fact: str
    why: str


class Out(BaseModel):
    items: list[Item]


def _compact(d, ctx):
    roster, teams = ctx.get("roster", {}), ctx.get("teams", {})
    out = {"insight_id": d["insight_id"], "kind": d["kind"], "subtype": d["subtype"],
           "team": teams.get(d["team"], {}).get("name", d["team"]),
           "players": [roster.get(p, {}).get("name", p) for p in d.get("players", [])],
           "show_t_s": d["show_t_s"], "metrics": {k: v["value"] for k, v in d["metrics"].items()},
           "claims": d["claims"], "importance_factors": d["importance"]["factors"]}
    if d.get("agent_context"):
        out["agent_context"] = mask_numbers(d["agent_context"])
    return out


def explain_insights(insights, match_context):
    """Insights without text -> {insight_id: {"fact": str, "why": str}} with {metric} placeholders (never digits or number words; special claims only if in the insight's `claims`).
    One call per match with all the insights. Without FOUNDRY_* returns {} so every insight uses its template. Errors propagate: explain_all falls back to templates."""
    global MODEL
    MODEL = None
    if not foundry.configured():
        return {}
    msg = json.dumps([_compact(d, match_context) for d in insights], ensure_ascii=False)
    out = foundry.run(INSTRUCTIONS, msg, response_format=Out, timeout_s=60)
    MODEL = os.environ["FOUNDRY_DEPLOYMENT"]
    return {i.insight_id: {"fact": i.fact, "why": i.why} for i in out.items}
