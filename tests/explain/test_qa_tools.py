import json
from pathlib import Path

from tacticai.explain.application import build_insights as B
from tacticai.explain.application import qa_tools as Q

FIX = Path(__file__).parent / "fixtures" / "match"
EVENTS = [json.loads(l) for l in (FIX / "interpret" / "events_enriched.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def session(events=EVENTS, insights=()):
    return Q.QASession(list(insights), events)


def test_every_goal_matches_the_real_goals():
    s = session()
    goals = [i for i, e in enumerate(EVENTS) if e["type"] == "goal"]
    assert goals
    assert s.count_events(type="goal") == {"count": len(goals)}
    assert [it["event_index"] for it in s.search_events(type="goal")["items"]] == goals


def test_interception_counts_for_the_interceptor_team():
    passer = [{"type": "pass", "t_s": 1.0, "team": "home", "player_id": "home-01", "outcome": "intercepted", "intercepted_by": "away-03"},
              {"type": "pass", "t_s": 2.0, "team": "home", "player_id": "home-02", "outcome": "complete", "intercepted_by": None}]
    s = session(passer)
    assert s.count_events(type="interception", team="away") == {"count": 1}
    assert s.count_events(type="interception", team="home") == {"count": 0}
    item = s.search_events(type="interception")["items"][0]
    assert (item["team"], item["player_id"]) == ("away", "away-03")
    assert s.count_events(type="pass", team="home") == {"count": 2}  # as passes they still belong to the passer


def test_pagination_and_half_open_interval():
    ev = [{"type": "pass", "t_s": float(i), "team": "home", "player_id": "p"} for i in range(5)]
    s = session(ev)
    first = s.search_events(limit=2)
    assert first["total"] == 5 and first["next_cursor"] == 2 and len(first["items"]) == 2
    last = s.search_events(limit=2, cursor=4)
    assert len(last["items"]) == 1 and last["next_cursor"] is None
    assert s.count_events(from_t_s=1.0, until_t_s=3.0) == {"count": 2}  # [1, 3)


def test_bad_enum_and_call_limit():
    s = session()
    assert s.count_events(type="dribble") == {"error": "invalid type 'dribble'", "valid": list(Q.TYPES)}
    assert s.search_moments(kind="nope")["valid"] == list(Q.KINDS)
    for _ in range(Q.MAX_TOOL_CALLS):
        s.count_events()
    assert "error" in s.count_events() and len(s.calls) == Q.MAX_TOOL_CALLS


def test_moments_and_validation(tmp_path):
    insights = B.build_insights(str(FIX))
    s = Q.QASession(insights, EVENTS)
    page = s.search_moments(kind="goal_or_chance")
    n = s.count_events(type="goal")["count"]
    iid = page["items"][0]["insight_id"]
    ok, errs = Q.validate_answer({"answer": "There was a goal chance and {n} goals", "values": {"n": n}, "moments": [{"kind": "insight", "insight_id": iid}]}, s, "en")
    assert not errs and ok["moments"][0]["period"] and "t_s" in ok["moments"][0] and str(n) in ok["answer"]
    assert Q.validate_answer({"answer": "x {n}", "values": {"n": 99}, "moments": []}, s, "en")[1]
    assert Q.validate_answer({"answer": "x", "values": {}, "moments": [{"kind": "event", "event_index": 0}]}, s, "en")[1]


def test_all_zero_gives_the_template():
    s = session()
    s.count_events(type="goal", period=9)
    out, errs = Q.validate_answer({"answer": "ignored"}, s, "es")
    assert not errs and out["answer"] == Q.NO_MOMENTS["es"] and out["moments"] == []


def test_string_and_null_numeric_args_are_coerced():
    ev = [{"type": "pass", "t_s": float(i), "team": "home", "player_id": "p", "period": 1, "lines_broken": 1} for i in range(5)]
    s = session(ev)
    bad = dict(from_t_s="1", until_t_s="4", period="1", min_lines_broken="1")
    assert s.count_events(**bad) == {"count": 3}
    assert s.search_events(**bad, limit="2", cursor="1")["total"] == 3
    assert s.count_events(from_t_s=None, until_t_s=None) == {"count": 5}
    assert s.search_moments(from_t_s="0", min_importance="0.5", limit="5")["total"] == 0
