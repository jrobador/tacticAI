"""Studio Script Agent: writes what the studio presenter reads aloud at full time, in one language, from the facts of the match
(fan_facts.py, without a side). The code validates every line and links each segment to its play in the video."""
import json

from pydantic import BaseModel

from ...agents import foundry

INSTRUCTIONS = """You write the full-time studio script of one football match: the words a TV presenter reads aloud in the studio, live, while the video of each play runs behind them. You receive the result, the plays of the match (each with a fact_id, its kind, the people in it and their roles, its details and its numbers as placeholders), the star player and the full-time awards.

Write for the ear, not for a page: short spoken sentences, present tense for the replays ("here is Corlune, one touch, and he scores"), a presenter's warmth and pace. Neutral: no side, no "we". Never a stats sheet: a number only when it tells the story, and always with its unit or noun.

Structure:
- opening: one or two sentences with the result and what decided it.
- segments: the three to five plays that told the story of the match, in playing order. Each segment is one play (its fact_id) and one or two sentences the presenter says while its replay runs. Prefer goals, shots and the plays that led to them.
- closing: one sentence on the star player or the awards, to hand over.

The roles and details of an item tell you what happened: say it in words, never read them out ("Corlune, the shooter", "the lines broken, 1"). `shot_from` is already a phrase: use it as it is.

Facts only: say only what the items contain (kinds, people and roles, details, numbers). Never invent where the ball went, how it was struck, the crowd, the referee, cards, injuries or tactics. Names: only those given in the item you are writing.
Numbers: never a digit or a number word; only the item's placeholders, exactly as written, each followed by its unit or noun; for a word after a count use "{n} {n|word|words}". Never write the minute.
Claims: opener / first goal only if the item's claims contain "first_goal"; equaliser / level only with "equaliser"; go-ahead / in front only with "go_ahead" (the same in every language).

If the input has `revise`, rewrite the whole script fixing every reason listed there.

<<LANGUAGE>>"""

LANGUAGE = {
    "en": "Output language: English, the register of a UK football studio show. Every word in English.",
    "es": "Output language: Spanish, the register of a Latin American football studio show (neutral, clear, warm). Every word in Spanish.",
}


class Segment(BaseModel):
    fact_id: str
    text: str


class Out(BaseModel):
    opening: str
    segments: list[Segment]
    closing: str


def write(brief, lang, revise=None):
    """`brief` = studio.brief(...); `revise` = [{"part", "text", "reason"}] for the second pass. -> {"opening", "segments": [{fact_id, text}],
    "closing"}; {} without FOUNDRY_*. Errors propagate."""
    if not foundry.configured():
        return {}
    msg = json.dumps({**brief, **({"revise": revise} if revise else {})}, ensure_ascii=False)
    out = foundry.run(INSTRUCTIONS.replace("<<LANGUAGE>>", LANGUAGE[lang]), msg, response_format=Out, timeout_s=120)
    return out.model_dump()
