import json
import shutil
from pathlib import Path

import pytest

from tacticai.explain.application import build_insights as B
from tacticai.explain.domain import placeholders as P
from tacticai.render.application import plans as plans_app
from tacticai.render.domain import director as D

FIX = Path(__file__).resolve().parents[1] / "explain" / "fixtures" / "match"


def jl(name):
    return [json.loads(l) for l in (FIX / "interpret" / name).read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture
def match(tmp_path):
    d = tmp_path / "m"
    shutil.copytree(FIX, d)
    return str(d)


@pytest.fixture
def insights(match):
    return B.run(match, context={})[0]


@pytest.fixture
def roster():
    return {p["player_id"]: p for p in json.loads((FIX / "roster.json").read_text(encoding="utf-8"))["players"]}


def syn(iid, show, imp, kind="lines_broken", team="home", players=(), subtype="goal"):
    return {"insight_id": iid, "kind": kind, "subtype": subtype, "team": team, "players": list(players), "show_t_s": show, "importance": {"value": imp},
            "metrics": {"lines_broken": {"value": 2, "unit": "lines"}, "passes": {"value": 3, "unit": "passes"}}, "claims": [],
            "text": {"fact": "Team broke {lines_broken} lines", "why": "In {passes} passes", "source": "template"}}


def variants_for(insights):
    return {f"{lens}_{lang}_{club}": {"texts": {i["insight_id"]: {"title": i["text"]["fact"], "text": i["text"]["why"], "source": "template"} for i in insights}}
            for lens in ("analyst", "fan", "first_match") for lang in ("en", "es") for club in ("neutral", "home", "away")}


def plans_for(insights, source="rules"):
    return {f"{l}_{c}": {"source": source, "overlays": D.rules_plan(insights, l, c)} for l in ("analyst", "fan", "first_match", "broadcast") for c in ("neutral", "home", "away")}


def call(insights, roster, lens="fan", club="neutral", player=None, metric=None, **kw):
    args = dict(insights=insights, plans=plans_for(insights or []), variants=variants_for(insights or []), lens=lens, lang="en", club=club, player=player, metric=metric,
                brand="tacticai", roster=roster, players_json=None, timeline=None, events=[])
    args.update(kw)
    return D.assemble_overlays(**args)


def max_concurrent(overlays):
    return max((sum(1 for o in overlays if o["show_t_s"] <= t < o["show_t_s"] + o["duration_s"]) for t in [o["show_t_s"] for o in overlays]), default=0)


def test_fan_never_two_at_once(insights, roster):
    many = [syn(f"i{k:03d}", 10 + k * 2, 0.9 - k * 0.01) for k in range(8)]
    for data in (insights, many):
        r = call(data, roster, "fan")
        assert r["overlays"] and max_concurrent(r["overlays"]) == 1
        assert all(o["slot"] == "bottom_left" for o in r["overlays"])


def test_analyst_never_more_than_three(roster):
    many = [syn(f"i{k:03d}", 10 + k, 0.9 - k * 0.01, kind=("lines_broken", "pressure_spell")[k % 2], subtype="peak" if k % 2 else "end") for k in range(12)]
    r = call(many, roster, "analyst")
    assert max_concurrent(r["overlays"]) == 3
    assert {o["slot"] for o in r["overlays"]} <= {"bottom_left", "top_right", "bottom_right"}


def test_broadcast_is_a_queue_without_slots(insights, roster):
    r = call(insights, roster, "broadcast", brand="bka-tv")
    assert len(r["overlays"]) == len(insights) and all(o["slot"] is None for o in r["overlays"])
    assert [o["show_t_s"] for o in r["overlays"]] == sorted(o["show_t_s"] for o in r["overlays"])
    assert r["brand_tokens"]["logo"] == "/crest-bka.png" and call(insights, roster, "fan")["brand_tokens"] is None
    first = next(i for i in insights if i["insight_id"] == r["overlays"][0]["insight_id"])
    assert set(r["overlays"][0]["metrics"]) == set(first["metrics"])


def test_invalid_agent_plans(insights):
    ok = [{"insight_id": "i002", "slot": "bottom_left", "duration_s": 6, "reason": "x"}]
    assert D.validate_plan(ok, insights, "fan") == []
    assert D.validate_plan([{**ok[0], "insight_id": "i999"}], insights, "fan")
    assert D.validate_plan(ok + [{"insight_id": "i003", "slot": "bottom_left", "duration_s": 6, "reason": "x"}], insights, "fan")  # overlap
    assert D.validate_plan([{**ok[0], "duration_s": 12}], insights, "fan")
    assert D.validate_plan([{**ok[0], "slot": "top_right"}], insights, "fan")
    assert D.validate_plan(ok + ok, insights, "fan")  # duplicate


def test_plans_run_falls_back_to_rules_on_bad_agent(match, insights):
    bad = lambda ins, rules, ctx: {k: [{"insight_id": "i999", "slot": None, "duration_s": 6, "reason": "x"}] for k in rules}
    w = plans_app.run(match, agent=bad, context={})
    d = Path(match) / "render" / "plans"
    files = sorted(d.glob("*.json"))
    assert len(files) == 12 and len(w) == 12
    assert {json.loads(f.read_text())["source"] for f in files} == {"rules"}
    assert plans_app.run(match, context={}) == []  # stub raises NotImplementedError: silent rules


def test_plans_run_uses_valid_agent_plan(match, insights):
    good = lambda ins, rules, ctx: {k: [{"insight_id": "i002", "slot": None if k.startswith("broadcast") else "bottom_left", "duration_s": 5, "reason": "x"}] for k in rules}
    assert plans_app.run(match, agent=good, context={}) == []
    p = json.loads((Path(match) / "render" / "plans" / "fan_home.json").read_text())
    assert p["source"] == "agent" and [o["insight_id"] for o in p["overlays"]] == ["i002"]


def test_player_focus_raises_priority_and_displaces_lower_non_player(roster):
    a = syn("i000", 10, 0.70, players=["away-04"], team="away")
    b = syn("i001", 12, 0.55, players=["home-09"])  # below the fan threshold without the bonus
    assert [o["insight_id"] for o in call([a, b], roster, "fan")["overlays"]] == ["i000"]
    r = call([a, b], roster, "fan", player="home-09")
    assert [o["insight_id"] for o in r["overlays"]] == ["i001"]
    assert r["overlays"][0]["priority"] == 0.8 and r["overlays"][0]["trail"]["director"] == "rules"
    assert r["player_card"]["insight_ids"] == ["i001"]
    strong = syn("i000", 10, 0.95, players=["away-04"], team="away")
    assert [o["insight_id"] for o in call([strong, b], roster, "fan", player="home-09")["overlays"]] == ["i000"]  # higher priority is not displaced
    mine = syn("i000", 10, 0.70, players=["home-09"])
    assert [o["insight_id"] for o in call([mine, b], roster, "fan", player="home-09")["overlays"]] == ["i000"]  # player overlays are never displaced


def test_one_metric_pressure_keeps_nulls(insights, roster):
    tl = jl("timeline.jsonl")
    r = call(insights, roster, "one_metric", metric="pressure", timeline=tl)
    ms = r["metric_series"]
    assert (ms["mode"], ms["unit"], ms["available"]) == ("windows", "0-1", True) and len(ms["points"]) == len(tl)
    assert ms["points"][0] == {"from_t_s": 1.8, "until_t_s": 3.6, "home": None, "away": 0.0}
    assert all(next(i for i in insights if i["insight_id"] == o["insight_id"])["kind"] == "pressure_spell" for o in r["overlays"])
    assert r["director"] == "rules" and r["metric"] == "pressure"
    poss = call(insights, roster, "one_metric", metric="possession", timeline=tl)
    assert poss["overlays"] == [] and poss["metric_series"]["points"][0]["home"] == 100.0 and poss["metric_series"]["points"][2]["home"] is None


def test_goals_added_attributes_interception_to_opponent(roster):
    ev = [{"type": "pass", "t_s": 5.0, "team": "home", "outcome": "intercepted", "vaep": {"total": -0.05}, "vaep_interception": {"total": 0.2}},
          {"type": "shot", "t_s": 7.0, "team": "away", "vaep": {"total": 0.1}}, {"type": "set_piece", "t_s": 8.0, "team": "away"}]
    r = call([syn("i000", 10, 0.9)], roster, "one_metric", metric="goals_added", events=ev)["metric_series"]
    assert r["mode"] == "steps" and r["points"] == [{"t_s": 0.0, "home": 0.0, "away": 0.0}, {"t_s": 5.0, "home": -0.05, "away": 0.2}, {"t_s": 7.0, "home": -0.05, "away": 0.3}]
    off = call([syn("i000", 10, 0.9)], roster, "one_metric", metric="goals_added", events=ev, has_vaep=False)["metric_series"]
    assert (off["available"], off["reason"], off["points"]) == (False, "vaep_model_missing", [])


def test_determinism_and_text_resolution(insights, roster):
    a, b = call(insights, roster, "analyst", "home", "home-09"), call(insights, roster, "analyst", "home", "home-09")
    assert json.dumps(a) == json.dumps(b)
    o = next(o for o in a["overlays"] if o["insight_id"] == "i002")
    assert "{" not in o["title"] + o["text"] and " 2 lines in 2 passes" in o["title"]
    assert set(call(insights, roster, "fan")["overlays"][0]["metrics"]) <= {"lines_broken", "xg", "value", "after", "mean_momentum"}
    assert len(call(insights, roster, "fan")["overlays"][0]["metrics"]) == 1
    assert P.fmt({"value": 2, "unit": "lines"}) == "2"


def test_available_false_and_bad_params(insights, roster):
    assert call(None, roster) == {"available": False, "reason": "not_enriched"}
    assert call(insights, roster, plans={}) == {"available": False, "reason": "not_enriched"}
    assert call(insights, roster, variants={}) == {"available": False, "reason": "not_enriched"}
    with pytest.raises(ValueError):
        call(insights, roster, "fan", metric="xg")
    with pytest.raises(ValueError):
        call(insights, roster, player="nobody")
