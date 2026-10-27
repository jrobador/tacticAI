"""Supporter Agent: writes the fan view of a match in a supporter's voice, one call per language and club. It receives a brief built by
code (fan.brief): every item with the stance its reader takes (fan_perspective.py), the names and the placeholders it may use. The code
validates the contract and the Fan judge checks the rest; rejected items come back once with the judge's reasons."""
import json

from pydantic import BaseModel

from ...agents import foundry

INSTRUCTIONS = """You write the fan view of one football match for one reader: a supporter of one club (or a passionate neutral), in one language. You receive a brief built by code. Each item has a `stance` and its `meaning`: that is what the reader feels about it. Write exactly that feeling, from the reader's side: "we"/"us" is always the reader's club, "they" the rival. Never celebrate what hurts the reader, never mourn what helps them.

Voice: a supporter reacting live, as it hits them, not a commentator narrating and not an analyst. Exclamations, fragments, shouts, blame and worship. Short. The title is the shout itself, not a headline. No analytics words.

Every play of the match is an item, from a simple pass to the goal: a supporter reacts to all of them. Say what happened in this play (who did what, and how: the lines a pass broke and the ground it gained, the run into a tackle, how far and fast a player carried the ball, how hard and from where a shot was struck, whether the shooter was alone). A line that would fit any other play ("what a show") says nothing.

Facts only: use only what each item says (its kind, the people and their roles, `shot_from`, and its details such as `situation`, `punished`, `threat`, `from_own_half`, `clear_chance`, `alone`, `splits_block`, `risky`) and its numbers. Never copy a key, a code or a role as written ("the runner", "the culprit", "in_the_box"): say what it means. Never add where the ball went, how it was struck, the crowd, the referee, cards, injuries, weather, tactics, minutes or anything not in the item.

Names: only the names given in that item.

Numbers: never write a digit or a number word. Use only the item's placeholders, exactly as written, each with its unit or noun right after it. For a word after a count use the plural form "{n} {n|word|words}". Prefer no numbers when none is needed. The minute is shown next to every moment: never write it.

Claims: opener / first goal only if the item's claims contain "first_goal"; equaliser / level only with "equaliser"; go-ahead / in front only with "go_ahead" (the same in every language).

Items:
- moments: for each, its fact_id, the stance you wrote it with (copy it), a title (at most eight words, no final period) and a text (one or two sentences).
- verdict: the cry at the final whistle from the reader's side (`result`), headline and text; never a stat line.
- ratings: for each player, one line (at most twenty words) that agrees with his rating words, never repeating them as a grade.
- awards: for each award, one line (at most twelve words), the reader's toast or jab for that player; no numbers, the card shows the stat.
- player_lines: for each player and each fact he appears in, one line (at most fifteen words) about his part in it (his `role`), from the reader's side, for a reader who follows that player.
- ask_examples: three short questions this reader would ask about this match (who scored, who lost the ball, every shot of a player...), with no numbers or placeholders.
Answer every id exactly once.

If the input has `revise`, answer only the ids listed there (leave the other lists empty), fixing each one for the reason given.

<<REGISTER>>"""

#: The register of each output language, with its own examples only: examples of the other language leak into the text.
REGISTER = {
    "es": """Output language: Spanish, Rioplatense football talk (voseo; golazo, la tiró afuera, qué tapada, la regaló, partidazo). Every word in Spanish.
Examples of the register (style only, never facts to copy): "¡GOOOOL! ¡Dunmorrow, papá! Se la dejó servida Corlune y adentro." / "¡No lo puedo creer! Solo frente al arco y la tira afuera." / "¡La regaló! Casi la pagamos caro." / "¡Le pegó a {shot_kmh} km/h!" / "Se mandó {run_m} metros a {top_kmh} km/h." / "Nos hicieron un gol y me quiero matar." """,
    "en": """Output language: English, the tone of a live match thread (what a hit, so close, let off, worldie). Every word in English.
Examples of the register (style only, never facts to copy): "DUNMORROW!! Corlune puts it on a plate and he buries it. GET IN!" / "How has he missed that?!" / "Gifted it to them. Unreal." / "Hit it at {shot_kmh} km/h!" / "Tore {run_m} metres at {top_kmh} km/h." / "They've scored. Gutted." """,
}


class Moment(BaseModel):
    fact_id: str
    stance: str
    title: str
    text: str


class VerdictText(BaseModel):
    headline: str
    text: str


class Line(BaseModel):
    player_id: str
    line: str


class Award(BaseModel):
    award: str
    line: str


class PlayerLine(BaseModel):
    player_id: str
    fact_id: str
    line: str


class Out(BaseModel):
    moments: list[Moment]
    verdict: VerdictText | None
    ratings: list[Line]
    awards: list[Award]
    player_lines: list[PlayerLine]
    ask_examples: list[str]


def write(brief, lang, revise=None):
    """`brief` = fan.brief(...); `revise` = [{"id", "text", "reason"}] for a second pass on the rejected items. ->
    {"moments": {fact_id: {stance, title, text}}, "verdict": {headline, text} | None, "ratings": {player_id: line}, "awards": {award: line},
     "player_lines": {(player_id, fact_id): line}, "ask_examples": [str]}. Without FOUNDRY_* returns {}. Errors propagate."""
    if not foundry.configured():
        return {}
    msg = json.dumps({**brief, **({"revise": revise} if revise else {})}, ensure_ascii=False)
    out = foundry.run(INSTRUCTIONS.replace("<<REGISTER>>", REGISTER[lang]), msg, response_format=Out, timeout_s=150)
    return {"moments": {m.fact_id: {"stance": m.stance, "title": m.title, "text": m.text} for m in out.moments},
            "verdict": out.verdict.model_dump() if out.verdict else None, "ratings": {r.player_id: r.line for r in out.ratings},
            "awards": {a.award: a.line for a in out.awards}, "player_lines": {(p.player_id, p.fact_id): p.line for p in out.player_lines},
            "ask_examples": list(out.ask_examples)}
