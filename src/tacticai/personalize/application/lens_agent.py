"""Lens Agent: one Foundry call per match writes, for every insight, the neutral English body (title, text) of each text lens. The code adds the side and the concept sentence."""
import json

from pydantic import BaseModel

from ...agents import foundry
from ...explain.application.explainer_agent import _compact
from ..domain.lenses import main_metric

INSTRUCTIONS = """You are a football writer who adapts the explanation of each key moment (insight) of one match to three audiences. You receive the insights of the match as JSON, each with its neutral explanation (`fact` and `why`, already written with {metric} placeholders) and its `main_metric`. For EACH insight write a title and a text for three lenses, in English.

Lenses:
- analyst: technical and precise, like a performance analyst. Mention every relevant metric of the insight, always through its placeholder.
- fan: emotional and lively, like someone watching with passion. Short sentences. Use only the insight's `main_metric` placeholder (no placeholder if it is null).
- first_match: plain everyday words for someone who has never watched football seriously. No jargon: if you need a football or analytics term, explain it in a few plain words. At most the `main_metric` placeholder.

Neutral body:
- Write each body so it works for any supporter: do not address the reader and do not take a side (no "your team", "your side", "the rival", "Yes!", "watch out").
- Do not add a sentence that explains the concept of the moment; the code adds it for first_match.
- title: short, at most eight words, a headline without final period. text: one or two sentences.
- Keep the same facts as the insight's `fact` and `why`; do not add anything that is not there.

Numbers:
- Never write a digit and never write a number word (one, two, three, zero, point, twelve...), even to spell out a value. The values in `metrics` are context only: NEVER copy or spell them; write the placeholder instead.
- Example: metrics {"lines_broken": 2, "passes": 3, "xg": 0.33} -> analyst text "Reds broke {lines_broken} {lines_broken|line|lines} in {passes} {passes|pass|passes}, and the move ended in a shot worth {xg} engine xG."
- Counts are the usual slip: "two lines", "three passes", "a couple of", "both" are all forbidden. If the sentence needs a count, always use its placeholder.
- Prefer wording without numbers when no metric is needed. Pressure and momentum values are on a 0-1 scale: refer to them only through placeholders such as {value}, {before}, {after}, {mean_momentum}.
- To mention a number, use a placeholder of that insight's OWN metrics, copied exactly from its `metrics` list: {xg}, {lines_broken}, {passes}, {value}...
- For the noun after a count use the plural form {metric|singular|plural}, for example "{lines_broken} {lines_broken|line|lines}" or "{passes} {passes|pass|passes}". Plural words contain no digits.
- Never use a placeholder that is not in that insight's metrics.

Claims:
- The words highest, peak, record only if the insight's claims contain "match_max".
- The words first goal, opener only if claims contain "first_goal".
- The word equaliser only if claims contain "equaliser".
- The words go-ahead, took the lead only if claims contain "go_ahead".
- If the claim is not present, do not imply it in other words either.

Style and limits:
- xG, xPass and goals added are engine values: say "engine xG" and never present them as official statistics.
- Physical values are relative to this match only. Never compare with other leagues or seasons (no Premier League comparisons).
- Describe temporal association only; never claim causality (no "because", "thanks to", "led to").
- Use team and player names as given. Do not invent facts, players, minutes or scores that are not in the input.
- Answer every insight_id exactly once, with the same id, and all three lenses."""


class Body(BaseModel):
    title: str
    text: str


class Item(BaseModel):
    insight_id: str
    analyst: Body
    fan: Body
    first_match: Body


class Out(BaseModel):
    items: list[Item]


def _input(d, ctx):
    return {**_compact(d, ctx), "main_metric": main_metric(d), "fact": d["text"]["fact"], "why": d["text"]["why"]}


def adapt_texts(insights, match_context):
    """-> {insight_id: {"analyst": {"title", "text"}, "fan": {...}, "first_match": {...}}}: neutral English bodies with {metric} placeholders (never digits or number words; special claims only
    if in the insight's `claims`). One call per match. Without FOUNDRY_* returns {} so every insight uses its template. Errors propagate: the caller falls back to templates."""
    if not foundry.configured():
        return {}
    msg = json.dumps([_input(d, match_context) for d in insights], ensure_ascii=False)
    out = foundry.run(INSTRUCTIONS, msg, response_format=Out, timeout_s=90)
    return {i.insight_id: {l: getattr(i, l).model_dump() for l in ("analyst", "fan", "first_match")} for i in out.items}
