"""Fan judge: one Foundry call that checks the Supporter agent's texts of one fan view against one rubric. Fails closed; never raises.
A new kind of mistake found in the fan view becomes a line of this rubric (and a case in tests/personalize/fan_cases.json), not a regex."""
import json
import os
from typing import Literal

from pydantic import BaseModel

from . import foundry

INSTRUCTIONS = """You judge texts written for football supporters. Every text comes with the brief it was written from: the output language, the club the reader supports (or neutral), the stance the text must take and its meaning, the facts and the names it may use. Judge every text by id.

Reject a text when any of these fails:
1. Language: every word is in the output language. A single word or phrase of another language rejects it (player and team names, "km/h" and "olé" are fine).
2. Stance: the text takes the stance of its brief, from the reader's side. A supporter never celebrates the rival's goal or cheers the rival's scorer; never mourns their own team's goal. "Us/we" is always the reader's club. A neutral reader has no "we": excitement about any goal and saying who won or deserved it are facts, not taking sides.
3. Facts only: the text says nothing the brief does not contain. Reject invented details: where the ball went in (top corner, near post), the kind of finish (header, volley, chip), the crowd, the referee, cards, injuries, the weather, tactics, other players or other moments. Plain emotion, insults to fate and football slang are not facts and are fine.
4. Voice: <<VOICE>>; no analytics words (xG, expected goals, VAEP, goals added, momentum, possession share, probability, metric, index). The text says what happened in its play (who did what): a line that would fit any other play ("loving the show", "what a game") is rejected. It never repeats the brief's description of the stance as a label ("swagger", "worship him", "the runner").
5. Numbers: every number placeholder ({name}) is followed by its unit or noun (km/h, metres/metros, passes/pases, sprints...), never bare or in brackets. The plural form {name|word|words} right after it is its noun ("{run_m} {run_m|metre|metres}" is fine). A score ({home_goals} and {away_goals} together) is fine however it is read: "{home_short} {home_goals}–{away_goals} {away_short}", "won {home_goals}-{away_goals}", "gana {home_goals} a {away_goals}".
6. Questions (ids starting "ask:"): several short questions separated by " | ", each one a question a supporter would ask about this match, in the output language; only rule 1 applies to them as well.

For every text return its id, verdict "ok" or "reject", the exact quote that breaks a rule (empty for ok) and which rule with a short reason (empty for ok). Return every id exactly once."""


#: Who the texts are written as: the rubric is the same, only the voice changes.
VOICES = {
    "supporter": "a supporter reacting, not a commentator narrating or an analyst",
    "presenter": "a TV studio presenter speaking to camera over the replays, written for the ear in full spoken sentences, neutral (no \"we\"); "
                 "never a stats sheet (\"the lines broken, 1\"), never a field or role name read out (\"the shooter\", \"the carrier\"). Rule 2 means: no side at all",
}


class Verdict(BaseModel):
    id: str
    verdict: Literal["ok", "reject"]
    quote: str
    reason: str


class Out(BaseModel):
    items: list[Verdict]


def judge(items, brief, timeout_s=90, voice="supporter") -> dict[str, str]:
    """items: [{"id", "text", "brief"}]; brief: what the whole view was written from (language, reader); voice: a key of VOICES.
    -> {id: reason} for the rejected ids."""
    if not items or not foundry.configured():
        return {}
    ids = [i["id"] for i in items]
    try:
        out = foundry.run(INSTRUCTIONS.replace("<<VOICE>>", VOICES[voice]), json.dumps({"view": brief, "texts": items}, ensure_ascii=False, default=str), response_format=Out,
                          timeout_s=timeout_s, deployment=os.environ.get("FOUNDRY_JUDGE_DEPLOYMENT") or None)
    except Exception as e:  # fail closed
        return {i: f"fan judge failed: {type(e).__name__}: {e}" for i in ids}
    by = {v.id: v for v in out.items}
    return {i: "no verdict" if i not in by else f"{by[i].quote!r}: {by[i].reason}" for i in ids if i not in by or by[i].verdict == "reject"}
