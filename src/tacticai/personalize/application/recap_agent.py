"""Recap Agent: one Foundry call per match writes the English recap of every (lens, club) that has moments, with {iNNN.metric} placeholders."""
import json

from pydantic import BaseModel

from ...agents import foundry
from ...explain.application.explainer_agent import _compact
from ..domain.lenses import main_metric

INSTRUCTIONS = """You are a football writer. You receive the key moments (insights) of one match as JSON and a list of recaps to write. Each recap has a `key`, a `lens`, a `club` and the `insight_ids` of its moments (chosen by the code, in playing order). For EACH recap write one short summary in English of 3 to 5 sentences that covers its moments in playing order, using only those insights.

Lenses:
- analyst: technical and precise; mention the relevant metrics of each moment.
- fan: emotional and lively; few numbers, only the main metric of a moment (`main_metric`).
- first_match: plain everyday words for someone who has never watched football seriously; explain any term in a few words; at most the main metric.

Club: `neutral` = even-handed, name both teams as needed. `home` or `away` = the recap is for supporters of that team (`club_name`): talk about its moments as its own and about the other team as the rival.

Numbers:
- Never write a digit and never write a number word (one, two, three, zero, point, twelve...), even to spell out a value. The values in `metrics` are context only: NEVER copy or spell them; write the placeholder instead.
- Placeholders in a recap carry the insight id: {i003.lines_broken}, {i003.xg}. Use only placeholders of the insights listed in THAT recap's `insight_ids`, copied exactly from the `metrics` of that insight. Never use a placeholder without the id.
- Example: insight i003 with metrics {"lines_broken": 2, "passes": 3} -> "Reds broke {i003.lines_broken} {i003.lines_broken|line|lines} in {i003.passes} {i003.passes|pass|passes}."
- Counts are the usual slip: "two lines", "three passes", "a couple of", "both" are all forbidden. If the sentence needs a count, always use its placeholder.
- Prefer wording without numbers when no metric is needed. Pressure and momentum values are on a 0-1 scale: refer to them only through placeholders.
- For the noun after a count use the plural form {iNNN.metric|singular|plural}. Plural words contain no digits.

Claims (per insight, from its `claims`):
- The words highest, peak, record only if that insight's claims contain "match_max".
- The words first goal, opener only if claims contain "first_goal".
- The word equaliser only if claims contain "equaliser".
- The words go-ahead, took the lead only if claims contain "go_ahead".
- If the claim is not present, do not imply it in other words either.

Style and limits:
- xG, xPass and goals added are engine values: say "engine xG" and never present them as official statistics.
- Physical values are relative to this match only. Never compare with other leagues or seasons.
- Describe temporal association only; never claim causality (no "because", "thanks to", "led to").
- Use team and player names as given. Do not invent facts, players, minutes or scores that are not in the input.
- Do not mention insight ids in the text.
- Answer every recap `key` exactly once, with the same key."""


class Item(BaseModel):
    key: str
    text: str


class Out(BaseModel):
    items: list[Item]


def write_recaps(insights, picks, match_context):
    """picks {"<lens>_<club>": [insight_id]} (only combinations with moments) -> {"<lens>_<club>": text} in English with {iNNN.metric} placeholders (never digits or number words; special claims only
    if in the claims of that insight). One call per match. Without FOUNDRY_* raises NotImplementedError: every recap uses its template. Other errors propagate."""
    if not foundry.configured():
        raise NotImplementedError("Foundry not configured")
    teams = match_context.get("teams", {})
    used = {i for ids in picks.values() for i in ids}
    ins = [{**_compact(d, match_context), "main_metric": main_metric(d), "fact": d["text"]["fact"], "why": d["text"]["why"]} for d in insights if d["insight_id"] in used]
    recaps = []
    for key, ids in picks.items():
        lens, club = key.rsplit("_", 1)
        recaps.append({"key": key, "lens": lens, "club": club, "club_name": teams.get(club, {}).get("name"), "insight_ids": ids})
    msg = json.dumps({"insights": ins, "recaps": recaps}, ensure_ascii=False)
    out = foundry.run(INSTRUCTIONS, msg, response_format=Out, timeout_s=90)
    return {i.key: i.text for i in out.items}
