"""LIVE eval of the Fan judge (real Foundry calls) on the cases found while reviewing the fan view. Run: TAI_LIVE=1 pytest tests/personalize/test_fan_eval.py -s
A new mistake in the fan view becomes a case here; if the judge misses it, its rubric (agents/fan_judge.py) changes, not a regex."""
import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("TAI_LIVE") != "1", reason="live Foundry eval; set TAI_LIVE=1")

CASES = json.loads((Path(__file__).parent / "fan_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[c["case"] for c in CASES])
def test_judge_on_known_cases(case):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
    from tacticai.agents import fan_judge
    rejected = fan_judge.judge([{"id": "m:f00", "text": case["text"], "brief": case["brief"]}], {"language": case["language"], "reader": case["reader"]})
    print(case["case"], "->", rejected or "ok")
    assert ("reject" if rejected else "ok") == case["expect"], rejected
