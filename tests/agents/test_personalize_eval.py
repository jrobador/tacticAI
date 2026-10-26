"""LIVE eval of Lens, Recap, Translator and Director (real Foundry calls). Run: TAI_LIVE=1 pytest tests/agents/test_personalize_eval.py -s"""
import json
import os
import shutil
from pathlib import Path

import pytest

from tacticai.explain.domain import placeholders as P

pytestmark = pytest.mark.skipif(os.environ.get("TAI_LIVE") != "1", reason="live Foundry eval; set TAI_LIVE=1")


def read(m, *parts):
    return json.loads(Path(m, *parts).read_text(encoding="utf-8"))


def test_live_personalize_and_plans(tmp_path):
    from dotenv import load_dotenv
    load_dotenv(r"C:\Github\tacticAI\.env", override=True)
    from tacticai.explain.application import build_insights as B
    from tacticai.personalize.application import build_personalize
    from tacticai.render.application import plans
    m = tmp_path / "m"
    shutil.copytree("data/matches/20261023-235553-f205", m)
    insights, _ = B.run(str(m))  # the Explainer, live
    by_id = {d["insight_id"]: d for d in insights}
    warnings = build_personalize.run(str(m))
    warnings += plans.run(str(m))
    print("warnings:", len(warnings))
    for w in warnings:
        print("  ", w)
    assert not any("failed" in w for w in warnings)
    share = {}
    for lang in ("en", "es"):
        vs = [read(m, "personalize", "variants", f"{l}_{lang}_{c}.json") for l in ("analyst", "fan", "first_match") for c in ("neutral", "home", "away")]
        n = sum(len(v["texts"]) for v in vs)
        share[lang] = sum(v["sources"].get("agent", 0) for v in vs) / n
        print(lang, "agent share", round(share[lang], 2))
    for name, iid in (("fan_{}_home", None), ("first_match_{}_neutral", None)):
        for lang in ("en", "es"):
            v = read(m, "personalize", "variants", name.format(lang) + ".json")
            for k in list(v["texts"])[:3]:
                t = v["texts"][k]
                print(name.format(lang), k, t["source"], "|", P.resolve_text(t["title"], by_id[k]["metrics"], lang=lang), "|", P.resolve_text(t["text"], by_id[k]["metrics"], lang=lang))
    for lang in ("en", "es"):
        r = read(m, "personalize", "recaps", f"fan_{lang}_home.json")
        print("recap fan", lang, r["source"], r["insight_ids"], "|", r["text"])
    srcs = [read(m, "render", "plans", f"{l}_{c}.json")["source"] for l in ("analyst", "fan", "first_match", "broadcast") for c in ("neutral", "home", "away")]
    print("plans from agent:", srcs.count("agent"), "of 12")
    print("plan fan_home:", json.dumps(read(m, "render", "plans", "fan_home.json")["overlays"]))
    assert share["en"] >= 0.8 and share["es"] >= 0.8
    assert srcs.count("agent") >= 10
