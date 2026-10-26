"""Offline test of the batched Director: a fake returns the 12 plans; an empty or invalid one falls back to the rules."""
import json
import shutil
from pathlib import Path

import pytest

from tacticai.explain.application import build_insights as B
from tacticai.render.application import plans as plans_app

FIX = Path(__file__).resolve().parents[1] / "explain" / "fixtures" / "match"


@pytest.fixture
def match(tmp_path):
    d = tmp_path / "m"
    shutil.copytree(FIX, d)
    B.run(str(d), context={})
    return d


def one(k, iid, show=None):
    return [{"insight_id": iid, "slot": None if k.startswith("broadcast") else "bottom_left", "duration_s": 5, "reason": "x"}]


def test_batched_director_empty_and_overlapping_plans_use_rules(match):
    seen = {}

    def fake(insights, rules, ctx):
        seen.update(rules)
        got = {k: one(k, "i002") for k in rules}
        got["fan_home"] = []  # empty
        got["fan_away"] = one("fan_away", "i002") + one("fan_away", "i003")  # i002 and i003 both show at 24.3 in bottom_left
        return got
    w = plans_app.run(str(match), agent=fake, context={})
    assert len(seen) == 12 and seen["fan_neutral"]["slots"] == ["bottom_left"] and seen["broadcast_home"]["slots"] == [] and "rules_plan" in seen["analyst_away"]
    assert len(w) == 2 and any("fan_home" in x and "empty" in x for x in w) and any("fan_away" in x and "overlaps" in x for x in w)
    src = {p.stem: json.loads(p.read_text())["source"] for p in (match / "render" / "plans").glob("*.json")}
    assert len(src) == 12 and {k for k, v in src.items() if v == "rules"} == {"fan_home", "fan_away"}
    assert [o["insight_id"] for o in json.loads((match / "render" / "plans" / "fan_neutral.json").read_text())["overlays"]] == ["i002"]


def test_director_failure_gives_one_warning_and_all_rules(match):
    def boom(*a):
        raise RuntimeError("timeout")
    w = plans_app.run(str(match), agent=boom, context={})
    assert len(w) == 1 and "timeout" in w[0]
    assert {json.loads(p.read_text())["source"] for p in (match / "render" / "plans").glob("*.json")} == {"rules"}


def test_missing_combo_uses_rules(match):
    w = plans_app.run(str(match), agent=lambda i, r, c: {k: one(k, "i002") for k in r if k != "analyst_home"}, context={})
    assert len(w) == 1 and "analyst_home" in w[0]
