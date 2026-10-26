import json
import os
import shutil

import pytest

from tacticai.agents import foundry
from tacticai.explain.application import build_insights as B, explainer_agent as E

F205 = "data/matches/20261023-235553-f205"


def _env(monkeypatch):
    for v in foundry._VARS:
        monkeypatch.setenv(v, "x")


def test_not_configured(monkeypatch):
    for v in foundry._VARS:
        monkeypatch.delenv(v, raising=False)
    assert E.explain_insights([], {}) == {}


def test_configured_maps_items(monkeypatch):
    _env(monkeypatch)
    seen = {}

    def fake(instr, msg, **kw):
        seen.update(kw, msg=msg)
        return E.Out(items=[E.Item(insight_id="i000", fact="f", why="w")])

    monkeypatch.setattr(foundry, "run", fake)
    ins = [{"insight_id": "i000", "kind": "k", "subtype": "s", "team": "home", "players": ["p1"], "show_t_s": 1.0,
            "metrics": {"xg": {"value": 0.3, "unit": "xG"}}, "claims": [], "importance": {"factors": {"rarity": 1}}, "agent_context": []}]
    ctx = {"teams": {"home": {"name": "Reds"}}, "roster": {"p1": {"name": "Ann"}}}
    assert E.explain_insights(ins, ctx) == {"i000": {"fact": "f", "why": "w"}}
    assert seen["timeout_s"] == 60 and '"Reds"' in seen["msg"] and '"Ann"' in seen["msg"] and E.MODEL == "x"


def test_model_reset_when_unconfigured(monkeypatch):
    _env(monkeypatch)
    monkeypatch.setattr(foundry, "run", lambda *a, **k: E.Out(items=[]))
    E.explain_insights([], {})
    assert E.MODEL == "x"
    for v in foundry._VARS:
        monkeypatch.delenv(v, raising=False)
    E.explain_insights([], {})
    assert E.MODEL is None


@pytest.mark.skipif(not os.path.isdir(F205), reason="needs data/matches")
def test_explain_all_validates_per_insight(monkeypatch, tmp_path):
    _env(monkeypatch)
    m = tmp_path / "m"
    shutil.copytree(F205, m)
    ins = B.build_insights(str(m))
    a, b = ins[0], ins[1]
    items = [E.Item(insight_id=a["insight_id"], fact="A short fact", why="Context for it"),
             E.Item(insight_id=b["insight_id"], fact="It happened 3 times", why="Context")]
    monkeypatch.setattr(foundry, "run", lambda *a_, **k: E.Out(items=items))
    names = {t: f"T{t}" for t in ("home", "away")}
    warnings = B.explain_all(ins, B.build_match_context(str(m)), names)
    assert ins[0]["text"]["source"] == "agent" and ins[1]["text"]["source"] == "template"
    assert any(b["insight_id"] in w and "rejected" in w and "digit" in w for w in warnings)


def test_compact_masks_agent_context_numbers():
    d = {"insight_id": "i000", "kind": "k", "subtype": "s", "team": "home", "show_t_s": 1.0, "metrics": {}, "claims": [],
         "importance": {"factors": {}}, "agent_context": [{"text": "gained 21.289 m, -3,5 s", "n": 4, "l": ["in 12 passes"]}]}
    out = E._compact(d, {})["agent_context"]
    assert out == [{"text": "gained # m, # s", "n": 4, "l": ["in # passes"]}]
    assert not any(c.isdigit() for c in json.dumps(out) if c != "4")
