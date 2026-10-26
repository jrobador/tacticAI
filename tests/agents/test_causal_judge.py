import asyncio

import pytest

from tacticai.agents import causal_judge as J, foundry

ITEMS = [{"id": "a", "text": "A then B."}, {"id": "b", "text": "A led to B."}]


def _on(monkeypatch, run):
    monkeypatch.setattr(foundry, "configured", lambda: True)
    monkeypatch.setattr(foundry, "run", run)


def V(id, verdict, quote="", reason=""):
    return J.Verdict(id=id, verdict=verdict, quote=quote, reason=reason)


def test_reject_maps_to_reason(monkeypatch):
    _on(monkeypatch, lambda *a, **k: J.Out(items=[V("a", "ok"), V("b", "reject", "led to", "causal verb")]))
    assert J.judge(ITEMS, {"c1": 1}) == {"b": "'led to': causal verb"}


def test_all_ok(monkeypatch):
    _on(monkeypatch, lambda *a, **k: J.Out(items=[V("a", "ok"), V("b", "ok")]))
    assert J.judge(ITEMS, {}) == {}


def test_missing_id_is_rejected(monkeypatch):
    _on(monkeypatch, lambda *a, **k: J.Out(items=[V("a", "ok")]))
    assert J.judge(ITEMS, {}) == {"b": "no verdict"}


def test_run_raising_rejects_everything(monkeypatch):
    def boom(*a, **k):
        raise TimeoutError("slow")
    _on(monkeypatch, boom)
    r = J.judge(ITEMS, {})
    assert set(r) == {"a", "b"} and all(v.startswith("causal judge failed: TimeoutError") for v in r.values())


def test_not_configured_or_empty_does_not_call(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("called")
    monkeypatch.setattr(foundry, "run", boom)
    assert J.judge(ITEMS, {}) == {}
    monkeypatch.setattr(foundry, "configured", lambda: True)
    assert J.judge([], {}) == {}


def test_deployment_from_env_and_message(monkeypatch):
    seen = {}

    def run(instructions, message, **k):
        seen.update(k, message=message)
        return J.Out(items=[V("a", "ok"), V("b", "ok")])
    _on(monkeypatch, run)
    J.judge(ITEMS, {"c1": 1})
    assert seen["deployment"] is None and seen["response_format"] is J.Out and '"texts"' in seen["message"] and '"c1"' in seen["message"]
    monkeypatch.setenv("FOUNDRY_JUDGE_DEPLOYMENT", "strong")
    J.judge(ITEMS, {})
    assert seen["deployment"] == "strong"


def test_foundry_run_passes_deployment(monkeypatch):
    seen = {}

    async def fake(*args):
        seen["args"] = args
        raise RuntimeError("stop")
    monkeypatch.setattr(foundry, "_run", fake)
    with pytest.raises(RuntimeError):
        foundry.run("i", "m", timeout_s=5, deployment="strong")
    assert seen["args"][-1] == "strong"
