"""LIVE eval of the Scenario agent: the 10 cases of the old spec. Run: TAI_LIVE=1 pytest tests/agents/test_scenario_eval.py -s"""
import os

import pytest

LIVE = os.environ.get("TAI_LIVE") == "1"
pytestmark = pytest.mark.skipif(not LIVE, reason="live: set TAI_LIVE=1")

if LIVE:  # loading .env at import would leak FOUNDRY_* into the offline tests
    from dotenv import load_dotenv

    load_dotenv(r"C:\Github\tacticAI\.env")
from tacticai.ingest.application import scenario_agent  # noqa: E402
from tacticai.ingest.application.catalog import catalog, check_recipe  # noqa: E402
from tacticai.ingest.domain import recipe as R  # noqa: E402

_cache = {}


def _run(text, recipe=None):
    out = scenario_agent.draft_recipe(text, recipe)
    print(f"\n[{text}] -> {out['summary']}\n  {out['recipe']}")
    assert check_recipe(out["recipe"]) == []
    return R.to_dict(R.from_dict(out["recipe"])), out["summary"].lower()


def _first():
    if "r" not in _cache:
        _cache["r"] = _run("Wexmoor counter-attack that ends in a goal")[0]
    return _cache["r"]


def _wanted(r):
    return (r["situation"] or {}).get("wanted", [])


def test_1_counter_goal():
    r = _first()
    s = r["situation"]
    assert r["mode"] == "situation" and s["template"] == "counter" and s["ball_owner"] == "away"
    assert "goal_by_team:away" in s["wanted"] and r["seeds"] >= 150


def test_2_home_right_shot():
    r, _ = _run("Brackenford attack down the right ending in a shot")
    s = r["situation"]
    assert s["template"] == "wing_attack_right" and s["ball_owner"] == "home" and 30 <= r["seeds"] <= 80
    assert any(w.startswith(("ends_in_shot", "shot_by_team")) for w in s["wanted"])


def test_3_away_left():
    r, _ = _run("Wexmoor attack down the left ending in a shot")
    assert r["situation"]["template"] == "wing_attack_left" and r["situation"]["ball_owner"] == "away"


def test_4_more_pressure():
    base = _first()
    r, _ = _run("more pressure from the home side", base)
    assert "more_pressure:home" in _wanted(r) and set(base["situation"]["wanted"]) <= set(_wanted(r))
    assert r["situation"]["template"] == "counter" and r["away"] == base["away"] and r["seeds"] == base["seeds"]


def test_5_more_possession():
    base = _first()
    r, _ = _run("more possession for Wexmoor", base)
    assert "more_possession:away" in _wanted(r) and set(base["situation"]["wanted"]) <= set(_wanted(r))
    assert r["home"] == base["home"] and r["seeds"] == base["seeds"]


def test_6_full_match():
    base = _first()
    r, _ = _run("make it a full match, 4-4-2 vs 3-5-2", base)
    assert r["mode"] == "full_match" and r["situation"] is None
    assert (r["home"]["formation"], r["away"]["formation"]) == ("4-4-2", "3-5-2")
    assert (r["home"]["style"], r["away"]["style"]) == (base["home"]["style"], base["away"]["style"])
    assert (r["home"]["level"], r["away"]["level"]) == (base["home"]["level"], base["away"]["level"])


def test_7_goal_by_known_player():
    name = next((p["name"] for p in catalog()["players"] if "mossvane" in p["name"].lower()), None)
    if name is None:
        pytest.skip("Mossvane not in the catalog players")
    r, summary = _run("goal by Mossvane with a bicycle kick")
    assert f"goal_by:{name}".lower() in [w.lower() for w in _wanted(r)]
    assert any(k in summary for k in ("bicycle", "kick", "detect"))


def test_8_unknown_player():
    r, summary = _run("goal by Zzyzx Qwertyuiop")
    assert not any(w.startswith("goal_by:") for w in _wanted(r))
    assert any(k in summary for k in ("not ", "no player", "unknown", "doesn", "cannot", "can't"))


def test_9_comeback():
    r, summary = _run("the away team comes back to win")
    assert r["mode"] == "full_match" and any(k in summary for k in ("cannot", "can't", "not possible", "unable", "not "))


def test_10_unknown_formation():
    r, summary = _run("play a 4-2-4")
    assert "4-2-4" in summary and "4-2-4" not in (r["home"]["formation"], r["away"]["formation"])
