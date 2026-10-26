import inspect
import json
import os
import shutil
import threading
import time

import pytest

from tacticai.agents import foundry
from tacticai.explain.application import qa_agent as qa, qa_tools

SRC = "data/matches/20261023-235553-f205"


def _session(tmp_path):
    if not os.path.isdir(SRC):
        pytest.skip("needs data/matches")
    m = tmp_path / "m"
    shutil.copytree(SRC, m)  # never touch data/
    rows = lambda p: [json.loads(x) for x in (m / p).read_text(encoding="utf-8").splitlines() if x]
    return qa_tools.QASession(rows("explain/insights.jsonl"), rows("interpret/events_enriched.jsonl"))


CTX = {"teams": {}, "players": [], "max_tool_calls": 6, "max_output_tokens": 800, "deadline_s": 20}


def test_not_configured_is_not_implemented(monkeypatch):
    monkeypatch.setattr(foundry, "configured", lambda: False)
    with pytest.raises(NotImplementedError):
        qa.answer_question("every goal", "en", None, CTX)


def test_configured_run_validates(monkeypatch, tmp_path):
    s = _session(tmp_path)
    monkeypatch.setattr(foundry, "configured", lambda: True)

    def fake_run(instructions, message, *, tools, response_format, **kw):
        assert kw["max_tool_calls"] == 6 and kw["max_output_tokens"] == 800
        r = next(t for t in tools if t.__name__ == "search_events")(type="pass", limit=1)
        n = r["total"]
        return qa.Out(answer="There were {n} passes.", values=[qa._Value(name="n", value=n)],
                      moments=[qa._Moment(kind="event", insight_id=None, event_index=r["items"][0]["event_index"])])

    monkeypatch.setattr(foundry, "run", fake_run)
    out = qa.answer_question("how many passes", "en", s, CTX)
    res, errors = qa_tools.validate_answer(out, s, "en")
    assert errors == [] and res["moments"][0]["kind"] == "event" and "passes" in res["answer"]


def test_tools_are_serial_and_keep_signature(tmp_path):
    s = _session(tmp_path)
    inside, peak = [0], [0]

    def slow(**kw):
        inside[0] += 1
        peak[0] = max(peak[0], inside[0])
        time.sleep(0.05)
        inside[0] -= 1
        return {}
    slow.__name__ = "slow"
    wrapped = qa._serial([slow, s.count_events])
    ts = [threading.Thread(target=wrapped[0]) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert peak[0] == 1
    assert "outcome" in inspect.signature(wrapped[1]).parameters
