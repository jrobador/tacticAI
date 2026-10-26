import json

import pytest

from tacticai.agents import foundry

VARS = ("FOUNDRY_ENDPOINT", "FOUNDRY_DEPLOYMENT", "FOUNDRY_API_KEY")


def test_configured(monkeypatch):
    for v in VARS:
        monkeypatch.setenv(v, "x")
    assert foundry.configured()
    monkeypatch.delenv("FOUNDRY_API_KEY")
    assert not foundry.configured()


def test_ids_cap_errors_and_preregistered(tmp_path):
    log = foundry.ToolLog(cap=4)

    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    def boom() -> dict:
        raise ValueError("bad")

    pre = log.call("add", add, a=1, b=2)
    assert pre["call_id"] == "c1" and pre["response"] == 3
    tools = log.wrap_all([add, boom])
    assert tools[0].__name__ == "add" and tools[0].__doc__ == "Add."
    assert tools[0](a=2, b=3) == {"call_id": "c2", "result": 5}
    assert tools[1]() == {"call_id": "c3", "error": "ValueError: bad"}
    assert tools[0](a=1, b=1) == {"call_id": "c4", "result": 2}
    assert tools[0](a=9, b=9) == {"error": "tool call limit reached (4)"}
    assert len(log.entries) == 4
    p = tmp_path / "log.jsonl"
    log.write(p)
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]
    assert [r["call_id"] for r in rows] == ["c1", "c2", "c3", "c4"]
    assert rows[0]["args"] == {"a": 1, "b": 2}


def test_dict_result_is_merged():
    log = foundry.ToolLog()
    t = log.wrap(lambda: {"valid": True}, "t")
    assert t() == {"call_id": "c1", "valid": True}


def test_options_classic_model_unchanged():
    assert foundry._options("gpt-4.1-mini", 300) == {"temperature": 0, "max_tokens": 300}
    assert foundry._options("gpt-4.1-mini", None) == {"temperature": 0}


def test_options_reasoning_model(monkeypatch):
    monkeypatch.delenv("FOUNDRY_REASONING_EFFORT", raising=False)
    assert foundry._options("gpt-5-mini", 300) == {"reasoning_effort": "low", "max_tokens": 300 * foundry._CAP_FACTOR}
    assert foundry._options("O3-mini", None) == {"reasoning_effort": "low"}
    monkeypatch.setenv("FOUNDRY_REASONING_EFFORT", "minimal")
    assert foundry._options("gpt-5-mini", None)["reasoning_effort"] == "minimal"
