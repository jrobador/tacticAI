"""Live eval against Foundry: TAI_LIVE=1 python -m pytest tests/agents/test_tactical_eval.py -s
Each match runs RUNS times (temperature 0 still varies). Drop warnings are allowed and printed; a failed run is not."""
import json
import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
RUNS = 3
pytestmark = pytest.mark.skipif(os.environ.get("TAI_LIVE") != "1", reason="live eval: set TAI_LIVE=1")


def _run(tmp_path, match_id, n):
    from dotenv import load_dotenv
    from tacticai.interpret.application.agents import run_agents
    load_dotenv(ROOT / ".env", override=True)
    dest = tmp_path / f"{match_id}-{n}"
    shutil.copytree(ROOT / "data" / "matches" / match_id, dest, ignore=shutil.ignore_patterns("video.mp4"))
    (dest / "interpret" / "agents.json").unlink(missing_ok=True)
    warnings = run_agents(str(dest))
    log = [json.loads(line) for line in (dest / "interpret" / "agents_log.jsonl").read_text(encoding="utf-8").splitlines()]
    path = dest / "interpret" / "agents.json"
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    t = (doc or {}).get("tactical") or {"phases": [], "key_notes": [], "summary": {"text": ""}}
    print(f"\n=== {match_id} run {n + 1}: warnings={warnings}\ncalls: " + "; ".join(f"{e['call_id']} {e['tool']} {e['args']}" for e in log[3:]))
    for p in t["phases"]:
        print("PHASE", p["candidate_id"], p["rank"], p["text"], p["evidence"])
    for k in t["key_notes"]:
        print("NOTE", k["note_index"], k["rank"], k["text"], k["evidence"])
    print("SUMMARY", t["summary"]["text"])
    return warnings, doc, t


def _check(match_id, tmp_path, quality):
    misses = []
    for n in range(RUNS):
        warnings, doc, t = _run(tmp_path, match_id, n)
        assert not [w for w in warnings if "failed" in w], warnings
        assert doc is not None and t["summary"]["text"].strip()
        misses += quality(n, t)
    return misses


def test_f205(tmp_path):
    counter = []

    def quality(n, t):
        counter.append(0 in [p["candidate_id"] for p in t["phases"]])
        print(f"run {n + 1}: counter phase (candidate_id 0) survived: {counter[-1]}")
        if 5 not in [k["note_index"] for k in t["key_notes"]]:
            print(f"QUALITY MISS run {n + 1}: big_chance note (note_index 5) missing")
            return [n]
        return []
    misses = _check("20261023-235553-f205", tmp_path, quality)
    print(f"counter phase survived {sum(counter)}/{RUNS}")
    assert not misses, f"big_chance note missing in runs {misses}"


def test_76bb_no_phases(tmp_path):
    def quality(n, t):
        assert t["phases"] == []
        return []
    _check("20261024-022921-76bb", tmp_path, quality)
