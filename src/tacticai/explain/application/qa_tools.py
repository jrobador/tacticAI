"""Match Q&A tools: deterministic search over insights and enriched events.
`QASession` is the `tools` object handed to the agent: it exposes search_moments, search_events and count_events, enforces the call limit and records
every call and what it returned, so `validate_answer` can check the agent's answer against it."""
from ..domain import placeholders

KINDS = ("lines_broken", "pressure_spell", "goal_or_chance", "momentum_shift")
TYPES = ("pass", "shot", "goal", "tackle", "set_piece", "interception")
TEAMS = ("home", "away")
OUTCOMES = ("complete", "intercepted", "goal", "no_goal")
MAX_TOOL_CALLS = 6
MAX_OUTPUT_TOKENS = 800
NO_MOMENTS = {"en": "No moments match that question", "es": "Ningún momento responde a esa pregunta"}


def _bad_enum(**pairs):
    """First (value, valid) whose value is not None and not in valid -> {"error", "valid"}, else None."""
    for name, (value, valid) in pairs.items():
        if value is not None and value not in valid:
            return {"error": f"invalid {name} {value!r}", "valid": list(valid)}
    return None


def _page(rows, limit, cursor):
    limit, off = max(1, min(int(limit), 100)), max(0, int(cursor or 0))
    return {"items": rows[off:off + limit], "total": len(rows), "next_cursor": off + limit if off + limit < len(rows) else None}


def _in_time(t, from_t_s, until_t_s):
    return t is not None and t >= from_t_s and (until_t_s is None or t < until_t_s)  # half-open [from, until)


def _view(index, e, as_interception=False):
    """Event as the tools show it; with `as_interception` an intercepted pass gets the opponent of the passer as `team` and the interceptor as `player_id`.
    Other types (and type=None) show the event as recorded, so an intercepted pass still counts as a pass of the passer."""
    v = {"event_index": index, "type": e["type"], "t_s": e["t_s"], "team": e.get("team"), "player_id": e.get("player_id"),
         "outcome": e.get("outcome"), "lines_broken": e.get("lines_broken")}
    if as_interception:
        v.update(type="interception", team={"home": "away", "away": "home"}.get(e.get("team")), player_id=e["intercepted_by"])
    return v


class QASession:
    def __init__(self, insights, events, max_tool_calls=MAX_TOOL_CALLS, max_output_tokens=MAX_OUTPUT_TOKENS):
        self.insights, self.events = {i["insight_id"]: i for i in insights}, list(events)
        self.max_tool_calls, self.max_output_tokens = max_tool_calls, max_output_tokens
        self.calls = []  # {"tool", "args", "ok", "numbers"}; ok=False for rejected calls
        self.numbers = set()  # every count and total returned
        self.insight_ids, self.event_indices = set(), set()  # every reference shown in an `items` list

    def _call(self, tool, args, fn):
        if len(self.calls) >= self.max_tool_calls:
            return {"error": f"tool call limit reached ({self.max_tool_calls})"}
        out = fn()
        ok = "error" not in out
        nums = [out[k] for k in ("count", "total") if k in out]
        self.calls.append({"tool": tool, "args": args, "ok": ok, "numbers": nums})
        if ok:
            self.numbers.update(nums)
            for it in out.get("items", ()):
                (self.insight_ids if "insight_id" in it else self.event_indices).add(it.get("insight_id", it.get("event_index")))
        return out

    def search_moments(self, kind=None, team=None, player_id=None, period=None, from_t_s=0.0, until_t_s=None, min_importance=0.0, limit=20, cursor=None):
        def run():
            bad = _bad_enum(kind=(kind, KINDS), team=(team, TEAMS))
            if bad:
                return bad
            rows = [i for i in self.insights.values()
                    if (kind is None or i["kind"] == kind) and (team is None or i.get("team") == team) and (player_id is None or player_id in i.get("players", ()))
                    and (period is None or i.get("period") == period) and _in_time(i["t_s"], from_t_s, until_t_s) and i["importance"]["value"] >= min_importance]
            rows.sort(key=lambda i: (i["t_s"], i["insight_id"]))
            return _page([{"insight_id": i["insight_id"], "kind": i["kind"], "show_t_s": i["show_t_s"], "team": i.get("team"), "players": i.get("players", []),
                           "importance": i["importance"]["value"]} for i in rows], limit, cursor)
        return self._call("search_moments", dict(kind=kind, team=team, player_id=player_id, period=period, from_t_s=from_t_s, until_t_s=until_t_s,
                                                 min_importance=min_importance, limit=limit, cursor=cursor), run)

    def _matching(self, type, team, player_id, period, from_t_s, until_t_s, min_lines_broken, outcome):
        bad = _bad_enum(type=(type, TYPES), team=(team, TEAMS), outcome=(outcome, OUTCOMES))
        if bad:
            return bad
        rows = []
        for i, e in enumerate(self.events):
            if type == "interception" and not (e["type"] == "pass" and e.get("intercepted_by")):
                continue
            v = _view(i, e, type == "interception")
            if ((type is None or v["type"] == type) and (team is None or v["team"] == team) and (player_id is None or v["player_id"] == player_id)
                    and (period is None or e.get("period") == period) and _in_time(e["t_s"], from_t_s, until_t_s)
                    and (min_lines_broken is None or (v["lines_broken"] or 0) >= min_lines_broken) and (outcome is None or v["outcome"] == outcome)):
                rows.append(v)
        return rows

    def search_events(self, type=None, team=None, player_id=None, period=None, from_t_s=0.0, until_t_s=None, min_lines_broken=None, outcome=None, limit=50, cursor=None):
        def run():
            rows = self._matching(type, team, player_id, period, from_t_s, until_t_s, min_lines_broken, outcome)
            return rows if isinstance(rows, dict) else _page(rows, limit, cursor)
        return self._call("search_events", dict(type=type, team=team, player_id=player_id, period=period, from_t_s=from_t_s, until_t_s=until_t_s,
                                                min_lines_broken=min_lines_broken, outcome=outcome, limit=limit, cursor=cursor), run)

    def count_events(self, type=None, team=None, player_id=None, period=None, from_t_s=0.0, until_t_s=None, min_lines_broken=None, outcome=None):
        def run():
            rows = self._matching(type, team, player_id, period, from_t_s, until_t_s, min_lines_broken, outcome)
            return rows if isinstance(rows, dict) else {"count": len(rows)}
        return self._call("count_events", dict(type=type, team=team, player_id=player_id, period=period, from_t_s=from_t_s, until_t_s=until_t_s,
                                               min_lines_broken=min_lines_broken, outcome=outcome), run)


def validate_answer(out, session, lang):
    """Agent output -> (result, errors). result = {"answer", "values", "moments"}: the answer resolved, each moment carrying t_s, clock_s and period."""
    ok = [c for c in session.calls if c["ok"]]
    if ok and all(n == 0 for c in ok for n in c["numbers"]) and any(c["numbers"] for c in ok):
        return {"answer": NO_MOMENTS[lang], "values": {}, "moments": []}, []
    if not (isinstance(out, dict) and isinstance(out.get("answer"), str) and isinstance(out.get("values"), dict) and isinstance(out.get("moments"), list)):
        return None, ["output must be {answer, values, moments}"]
    values = out["values"]
    errors = [f"value {k!r} is not a count or total returned by a tool" for k, v in values.items() if isinstance(v, bool) or not isinstance(v, int) or v not in session.numbers]
    metrics = {k: {"value": v, "unit": "count"} for k, v in values.items() if isinstance(v, int) and not isinstance(v, bool)}
    errors += placeholders.validate_text(out["answer"], metrics, [], lang)
    moments = []
    for m in out["moments"]:
        if isinstance(m, dict) and m.get("kind") == "insight" and m.get("insight_id") in session.insight_ids:
            src = session.insights[m["insight_id"]]
            moments.append({"kind": "insight", "insight_id": m["insight_id"], "t_s": src["t_s"], "clock_s": src["clock_s"], "period": src["period"]})
        elif isinstance(m, dict) and m.get("kind") == "event" and m.get("event_index") in session.event_indices:
            src = session.events[m["event_index"]]
            moments.append({"kind": "event", "event_index": m["event_index"], "t_s": src["t_s"], "clock_s": src["clock_s"], "period": src["period"]})
        else:
            errors.append(f"moment {m!r} was not returned by a tool")
    if errors:
        return None, errors
    return {"answer": placeholders.resolve_text(out["answer"], metrics, None, lang), "values": values, "moments": moments}, []
