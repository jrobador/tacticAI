"""Translator Agent: one Foundry call per match turns the English Lens bodies and recaps (placeholders unresolved) into Spanish, same keys."""
import json
from collections import Counter

from pydantic import BaseModel

from ...agents import foundry
from ...explain.domain.placeholders import PLACEHOLDER

INSTRUCTIONS = """You are a professional football translator. You receive a list of short English texts, each with a `key`, and translate every one into natural, neutral Spanish that reads well in both Spain and Latin America (Rioplatense-neutral: no regional slang, no voseo forms).

Placeholders:
- Texts contain placeholders in curly braces: {lines_broken}, {i003.xg}, {lines_broken|line|lines}. Keep every placeholder exactly as it is, the same ones, the same number of times.
- A plural placeholder {metric|singular|plural} keeps its metric name and its two words are translated: {lines_broken|line|lines} -> {lines_broken|línea|líneas}; {passes|pass|passes} -> {passes|pase|pases}. Keep the two words in the same order: singular first, then plural.
- Never translate or change the metric name inside a placeholder. Never add a placeholder that is not in the original.

Numbers and claims:
- Never write a digit and never write a number word (uno, dos, tres, cero, diez, cien...), even to spell out a value. Do not turn words like "both" into "los dos"; rephrase without a number.
- Use claim words only when the original has them: highest / peak / record -> más alta / pico / récord only if the original says it; first goal / opener -> primer gol only if the original says it; equaliser -> igualó; go-ahead / took the lead -> puso arriba.
- Team and player names stay unchanged.
- Keep the meaning, the tone and the length of the original; translate "engine xG" as "xG del motor". Do not add or remove facts.
- Answer every `key` exactly once, with the same key."""


class Item(BaseModel):
    key: str
    text: str


class Out(BaseModel):
    items: list[Item]


def body_key(insight_id, lens, field):
    return f"{insight_id}.{lens}.{field}"


def recap_key(combo):
    return f"recap.{combo}"


def same_placeholders(a, b):
    """The two texts use the same metrics the same number of times, values and plural selectors counted apart (plural words may differ)."""
    count = lambda s: Counter((m.group(1), m.group(2), m.group(3) is not None) for m in PLACEHOLDER.finditer(s))
    return count(a) == count(b)


def translate(texts, match_context):
    """{key: English text with placeholders} -> {key: Spanish text}, same keys. One call per match. Without FOUNDRY_* (or no texts) returns {}. Errors propagate: the caller uses the Spanish templates."""
    if not foundry.configured() or not texts:
        return {}
    msg = json.dumps([{"key": k, "text": t} for k, t in texts.items()], ensure_ascii=False)
    out = foundry.run(INSTRUCTIONS, msg, response_format=Out, timeout_s=90)
    return {i.key: i.text for i in out.items}
