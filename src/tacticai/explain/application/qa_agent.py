"""Match Q&A agent: one Foundry run with the three QASession tools; the backend validates the answer (`qa_tools.validate_answer`).

answer_question(question, lang, tools, match_context) -> {"answer": str, "values": {name: int}, "moments": [{"kind": "insight", "insight_id"} | {"kind": "event", "event_index"}]}
- `tools` is the `qa_tools.QASession`: tools.search_moments / search_events / count_events (at most `max_tool_calls`; later calls return {"error"}).
- `answer` carries `{name}` placeholders only, never a digit or a number word; every `values` entry must equal a `count` or `total` a tool returned.
- every moment must have appeared in the `items` of a tool result.
- `match_context` = {"teams", "players", "max_tool_calls", "max_output_tokens", "deadline_s"}.
- Raises NotImplementedError without FOUNDRY_* (the API answers 501)."""
import functools
import json
import threading
from typing import Literal

from pydantic import BaseModel

from ...agents import foundry

INSTRUCTIONS = """You answer one question about one football match, using only the results of your tools. Write the answer in {lang_name}.

Tools:
- search_moments: the match's key moments (insights), filtered. Only the most important moments are indexed.
- search_events: every pass, shot, goal, tackle, set piece and interception of the match, filtered. Items have event_index.
- count_events: how many events match a filter ({{"count": n}}).
- For exhaustive questions ("every goal", "all the times...", "how many...") use search_events and count_events, not just search_moments. Use search_moments for "key moments", "best chances" and similar.
- Goals are the events of type "goal" (search_events type="goal"); the shot that scored is a different event, do not cite it as the goal.
- "interception" events are passes intercepted by the opponent: their team is the interceptor's side and their player_id is the interceptor. A pass that was intercepted still counts as a pass of the passer.
- team is "home" or "away"; player_id comes from the players list in the match context. Time is in seconds of the video (t_s). Use at most {max_calls} tool calls in total; plan the filters first. If a tool returns an error, fix the arguments or answer without it.

Answer format (strict; a program checks it):
- The answer text contains NO digits and NO number words (one, two, once, twice, a couple, both, first...). Every count is a placeholder in braces whose name is a key of `values`.
- Example. Tool result {{"total": 3}} for goals by Wexmoor. Answer: "Wexmoor scored {{goals}} {{goals|goal|goals}}." values: [{{"name": "goals", "value": 3}}]. The same holds when the count is 1: still "{{goals}} {{goals|goal|goals}}", never "1 goal" or "a goal".
- Each value must be exactly a `count` or `total` a tool returned in this question. If you need a count, call count_events or use the `total` of a search.
- Never write minutes, seconds, clock times, scores or jersey numbers. The moments list already shows when things happened. If no placeholder fits, rephrase without any number ("Corlune scored for Brackenford.").
- `moments`: the insights or events that support the answer, only ones that appeared in the `items` of a tool result. kind is "insight" (set insight_id, event_index null) or "event" (set event_index, insight_id null). Empty list if the answer needs none.
- Use team and player names from the match context. Do not invent facts. Never claim causality.
- Keep it short: 2 to 4 sentences. If nothing matches, say so briefly with no placeholders and no moments.
"""

_LANG = {"en": "English", "es": "Spanish"}


class _Value(BaseModel):
    name: str
    value: int


class _Moment(BaseModel):
    kind: Literal["insight", "event"]
    insight_id: str | None
    event_index: int | None


class Out(BaseModel):
    answer: str
    values: list[_Value]
    moments: list[_Moment]


def _serial(fns):
    """The tools share one QASession (not thread-safe) and the framework may run tool calls of one turn in parallel: one lock for all."""
    lock = threading.Lock()

    def wrap(fn):
        @functools.wraps(fn)
        def tool(**kwargs):
            with lock:
                return fn(**kwargs)
        return tool
    return [wrap(f) for f in fns]


def answer_question(question, lang, tools, match_context):
    if not foundry.configured():
        raise NotImplementedError("the Q&A agent needs FOUNDRY_*")
    instructions = INSTRUCTIONS.format(lang_name=_LANG[lang], max_calls=match_context["max_tool_calls"])
    msg = json.dumps({"question": question, "reminder": "no digits or number words in the answer: counts only as {name} placeholders listed in values", "match": {"teams": match_context["teams"], "players": match_context["players"]}}, ensure_ascii=False)
    out = foundry.run(instructions, msg, tools=_serial([tools.search_moments, tools.search_events, tools.count_events]), response_format=Out,
                      timeout_s=15, max_tool_calls=match_context["max_tool_calls"], max_output_tokens=match_context["max_output_tokens"])
    moments = [{"kind": m.kind, "insight_id": m.insight_id} if m.kind == "insight" else {"kind": m.kind, "event_index": m.event_index} for m in out.moments]
    return {"answer": out.answer, "values": {v.name: v.value for v in out.values}, "moments": moments}


answer_question.needs_foundry = True  # the API answers 501 before any limit counts when FOUNDRY_* is missing; injected fakes have no such attribute
