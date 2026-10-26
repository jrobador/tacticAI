"""LIVE eval of the Q&A agent (real Foundry calls). Run: TAI_LIVE=1 pytest tests/agents/test_qa_eval.py -s"""
import json
import os
import shutil

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("TAI_LIVE") != "1", reason="live Foundry eval; set TAI_LIVE=1")

QUESTIONS = [("en", "Show me every goal"), ("es", "¿Cuántos pases completó Wexmoor?"), ("en", "When did Brackenford break the press?")]


@pytest.fixture
def match(tmp_path):
    shutil.copytree("data/matches/20261023-235553-f205", tmp_path / "m")
    return tmp_path / "m"


def _rows(m, p):
    return [json.loads(x) for x in (m / p).read_text(encoding="utf-8").splitlines() if x]


def _ask(m, lang, q):
    from dotenv import load_dotenv
    load_dotenv(r"C:\Github\tacticAI\.env", override=True)
    from tacticai.explain.application import qa_agent, qa_tools
    s = qa_tools.QASession(_rows(m, "explain/insights.jsonl"), _rows(m, "interpret/events_enriched.jsonl"))
    meta = json.loads((m / "meta.json").read_text(encoding="utf-8"))
    ctx = {"teams": meta["teams"], "players": json.loads((m / "roster.json").read_text(encoding="utf-8"))["players"],
           "max_tool_calls": s.max_tool_calls, "max_output_tokens": s.max_output_tokens, "deadline_s": 20}
    out = qa_agent.answer_question(q, lang, s, ctx)
    res, errors = qa_tools.validate_answer(out, s, lang)
    print(f"\n[{lang}] {q}\n  raw: {out}\n  calls: {[(c['tool'], {k: v for k, v in c['args'].items() if v not in (None, 0.0, 0)}) for c in s.calls]}\n  answer: {res and res['answer']}\n  errors: {errors}")
    assert errors == [], errors
    return res, s


@pytest.mark.parametrize("lang,q", QUESTIONS)
def test_live_qa_validates(match, lang, q):
    _ask(match, lang, q)


def test_live_every_goal_is_exact(match):
    res, s = _ask(match, "en", "Show me every goal")
    goals = {i for i, e in enumerate(s.events) if e["type"] == "goal"}
    assert goals and {m["event_index"] for m in res["moments"] if m["kind"] == "event"} == goals
