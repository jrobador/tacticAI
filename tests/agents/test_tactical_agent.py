import json
import os
import shutil
from pathlib import Path

import pytest

from tacticai.agents import foundry
from tacticai.explain.domain.moments import with_agent_context
from tacticai.interpret.application import agents
from tacticai.interpret.application.agents import KeyNote, Phase, Summary, Tactical, run_agents

SRC = Path(__file__).parents[2] / "data" / "matches" / "20261023-235553-f205"
KEY = "{c1:results.match.effective_time_s}"


def _match(tmp_path, monkeypatch):
    if not SRC.is_dir():
        pytest.skip("needs data/matches")
    dest = tmp_path / "m"
    shutil.copytree(SRC, dest, ignore=shutil.ignore_patterns("video.mp4"))
    (dest / "interpret" / "agents.json").unlink(missing_ok=True)
    monkeypatch.setattr(foundry, "configured", lambda: True)
    monkeypatch.setenv("FOUNDRY_DEPLOYMENT", "test-model")
    monkeypatch.setattr(agents.causal_judge, "judge", lambda *a, **k: {})  # the judge has its own tests
    return str(dest)


def tactical(phases=None, notes=None, summary=f"Effective time was {KEY} s."):
    return Tactical(phases=phases if phases is not None else [Phase(candidate_id=0, rank=1, text=f"Counter over {KEY} s of effective time.")],
                    key_notes=notes if notes is not None else [KeyNote(note_index=0, rank=1, text=f"Opening note, {KEY} s effective.")],
                    summary=Summary(text=summary))


def fake(out):
    def run(instructions, message, **kw):
        assert "c1:results.match.effective_time_s = 29.0" in message and "citable:" in message
        assert kw["response_format"] is Tactical and len(kw["tools"]) == 7
        return out
    return run


def written(d):
    return json.loads(Path(d, "interpret", "agents.json").read_text(encoding="utf-8"))


def test_writes_agents_json_with_evidence_from_the_log(tmp_path, monkeypatch):
    d = _match(tmp_path, monkeypatch)
    monkeypatch.setattr(foundry, "run", fake(tactical()))
    assert run_agents(d) == []
    doc = written(d)
    assert doc["agents_version"] == 1 and doc["model"] == "test-model" and doc["quality"] is None
    p = doc["tactical"]["phases"][0]
    assert p["text"] == "Counter over 29.0 s of effective time." and p["evidence"] == [{"call_id": "c1", "path": "results.match.effective_time_s", "value": 29.0}]
    log = Path(d, "interpret", "agents_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["call_id"] for line in log] == ["c1", "c2", "c3"]
    cands = [{"refs": {"note_index": 0}, "team": "home", "t_s": 14.0, "until_t_s": 15.0}]
    phases = [{"candidate_id": 0, "team": "home", "from_t_s": 13.5, "until_t_s": 18.5}]
    assert [c["ref"] for c in with_agent_context(cands, doc, phases)[0]["agent_context"]] == ["key_note", "phase"]


def test_bad_items_are_dropped_and_the_rest_reranked(tmp_path, monkeypatch):
    d = _match(tmp_path, monkeypatch)
    notes = [KeyNote(note_index=0, rank=1, text="Unknown {c1:results.nope} key."), KeyNote(note_index=1, rank=2, text="A digit 5 outside."),
             KeyNote(note_index=2, rank=3, text=f"Fine {KEY}."), KeyNote(note_index=99, rank=4, text="Out of range."), KeyNote(note_index=3, rank=5, text="Both teams.")]
    monkeypatch.setattr(foundry, "run", fake(tactical(notes=notes)))
    warnings = run_agents(d)
    assert [n["note_index"] for n in written(d)["tactical"]["key_notes"]] == [2, 3] and [n["rank"] for n in written(d)["tactical"]["key_notes"]] == [1, 2]
    assert any("dropped key_notes[0] (unknown placeholder" in w for w in warnings) and any("digit outside" in w for w in warnings) and any("out of range" in w for w in warnings)


def test_bad_summary_fails_the_run(tmp_path, monkeypatch):
    d = _match(tmp_path, monkeypatch)
    monkeypatch.setattr(foundry, "run", fake(tactical(summary="Pressed 62% of the time.")))
    assert run_agents(d)[0].startswith("tactical agent failed: ValueError: summary")
    assert not os.path.exists(os.path.join(d, "interpret", "agents.json"))


def test_nothing_valid_fails_the_run(tmp_path, monkeypatch):
    d = _match(tmp_path, monkeypatch)
    out = tactical(phases=[Phase(candidate_id=0, rank=1, text="Digit 5.")], notes=[KeyNote(note_index=0, rank=1, text="Digit 6.")])
    monkeypatch.setattr(foundry, "run", fake(out))
    assert run_agents(d)[0].startswith("tactical agent failed:") and not os.path.exists(os.path.join(d, "interpret", "agents.json"))


def test_failure_is_a_warning(tmp_path, monkeypatch):
    d = _match(tmp_path, monkeypatch)

    def boom(*a, **k):
        raise TimeoutError("slow")
    monkeypatch.setattr(foundry, "run", boom)
    warnings = run_agents(d)
    assert len(warnings) == 1 and warnings[0].startswith("tactical agent failed:")
    assert not os.path.exists(os.path.join(d, "interpret", "agents.json"))


def test_not_configured(monkeypatch):
    monkeypatch.delenv("FOUNDRY_API_KEY", raising=False)
    assert agents.run_agents("nowhere") == ["agents not implemented"]


def _judge(monkeypatch, rejected):
    monkeypatch.setattr(agents.causal_judge, "judge", lambda items, data, **k: {i["id"]: rejected[i["id"]] for i in items if i["id"] in rejected})


def test_causal_rejected_note_is_dropped_and_reranked(tmp_path, monkeypatch):
    d = _match(tmp_path, monkeypatch)
    notes = [KeyNote(note_index=0, rank=1, text=f"First {KEY}."), KeyNote(note_index=2, rank=2, text=f"Second {KEY}."), KeyNote(note_index=3, rank=3, text="Both teams.")]
    monkeypatch.setattr(foundry, "run", fake(tactical(notes=notes)))
    _judge(monkeypatch, {"key_notes[0]": "'led to': causal"})
    warnings = run_agents(d)
    assert [(n["note_index"], n["rank"]) for n in written(d)["tactical"]["key_notes"]] == [(2, 1), (3, 2)]
    assert warnings == ["tactical agent: dropped key_notes[0] (causal: 'led to': causal)"]


def test_causal_rejected_summary_fails_the_run(tmp_path, monkeypatch):
    d = _match(tmp_path, monkeypatch)
    monkeypatch.setattr(foundry, "run", fake(tactical()))
    _judge(monkeypatch, {"summary": "bad"})
    assert run_agents(d) == ["tactical agent failed: ValueError: summary: causal: bad"]
    assert not os.path.exists(os.path.join(d, "interpret", "agents.json"))


def test_causal_rejecting_everything_fails_the_run(tmp_path, monkeypatch):
    d = _match(tmp_path, monkeypatch)
    monkeypatch.setattr(foundry, "run", fake(tactical()))
    _judge(monkeypatch, {"phases[0]": "x", "key_notes[0]": "y"})
    assert run_agents(d)[0].startswith("tactical agent failed: ValueError: no valid phase or key note")
