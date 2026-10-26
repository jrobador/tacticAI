"""LIVE eval of the Explainer (real Foundry call). Run: TAI_LIVE=1 pytest tests/agents/test_explainer_eval.py -s"""
import os
import shutil

import pytest

from tacticai.explain.domain import placeholders as P

pytestmark = pytest.mark.skipif(os.environ.get("TAI_LIVE") != "1", reason="live Foundry eval; set TAI_LIVE=1")


def test_live_explainer(tmp_path):
    from dotenv import load_dotenv
    load_dotenv(r"C:\Github\tacticAI\.env", override=True)
    from tacticai.explain.application import build_insights as B, explainer_agent
    m = tmp_path / "m"
    shutil.copytree("data/matches/20261023-235553-f205", m)
    insights, warnings = B.run(str(m))
    for d in insights:
        t = d["text"]
        print(d["insight_id"], d["kind"], d["subtype"], t["source"])
        print("  fact:", P.resolve_text(t["fact"], d["metrics"]))
        print("  why: ", P.resolve_text(t["why"], d["metrics"]))
    print("warnings:", warnings)
    assert not any("explainer failed" in w for w in warnings)
    assert explainer_agent.MODEL
    assert sum(d["text"]["source"] == "agent" for d in insights) >= 0.8 * len(insights)
