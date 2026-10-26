import json
import re
import shutil
from itertools import product
from pathlib import Path

import pytest

from tacticai.explain.application import build_insights as B
from tacticai.explain.domain import placeholders as P
from tacticai.personalize.application import build_personalize, recaps, variants
from tacticai.personalize.domain import lenses, templates

FIX = Path(__file__).resolve().parents[1] / "explain" / "fixtures" / "match"
NAMES = {"home": "Brackenford Athletic", "away": "Wexmoor City"}
KEYS = [("lines_broken", s) for s in ("goal", "shot", "lost", "out", "end_of_period")] + [("pressure_spell", s) for s in ("shift_up", "shift_down", "peak")] + \
       [("goal_or_chance", s) for s in ("goal", "chance_scored", "chance_missed")] + [("momentum_shift", s) for s in ("swing", "dominance")]
M = lambda v, u: {"value": v, "unit": u}
METRICS = {
    "lines_broken": {"lines_broken": M(1, "lines"), "passes": M(1, "passes"), "duration_s": M(9.7, "s"), "xg": M(0.335, "engine xG")},
    "pressure_spell": {"before": M(0.2, "0-1"), "after": M(0.61, "0-1"), "value": M(0.61, "0-1"), "match_mean": M(0.31, "0-1")},
    "goal_or_chance": {"xg": M(0.335, "engine xG")},
    "momentum_shift": {"before": M(0.1, "momentum"), "after": M(0.7, "momentum"), "mean_momentum": M(0.7, "momentum"), "xg": M(0.8, "engine xG"), "final_third_entries": M(1, "entries")},
}


def synth(i, kind, subtype, team="home", claims=(), importance=0.5, show=10.0, metrics=None):
    return {"insight_id": f"i{i:03d}", "kind": kind, "subtype": subtype, "team": team, "players": [], "t_s": show - 1, "until_t_s": show, "show_t_s": show, "clock_s": 10.0, "period": 1,
            "metrics": json.loads(json.dumps(METRICS[kind])) if metrics is None else metrics, "refs": {}, "claims": list(claims), "importance": {"value": importance, "factors": {}}}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("p") / "m"
    shutil.copytree(FIX, d)
    insights, _ = B.run(str(d), context={})
    warnings = build_personalize.run(str(d), context={})
    return d, insights, warnings


def names():
    return sorted(variants.variant_name(l, g, c) for l, g, c in product(lenses.TEXT_LENSES, lenses.LANGS, lenses.CLUBS))


def test_18_variants_and_18_recaps_exist(built):
    d, _, warnings = built
    assert warnings == []  # the stubs are silent
    assert len(names()) == 18
    assert sorted(p.stem for p in (d / "personalize" / "variants").glob("*.json")) == names()
    assert sorted(p.stem for p in (d / "personalize" / "recaps").glob("*.json")) == names()
    assert not list((d / "personalize").rglob("*.tmp"))


def test_every_insight_has_text_in_every_variant_and_stub_is_all_template(built):
    d, insights, _ = built
    for n in names():
        v = json.loads((d / "personalize" / "variants" / f"{n}.json").read_text(encoding="utf-8"))
        assert v["variant_version"] == 1 and f"{v['lens']}_{v['lang']}_{v['club']}" == n
        assert set(v["texts"]) == {i["insight_id"] for i in insights}
        assert all(t["source"] == "template" and t["title"] and t["text"] for t in v["texts"].values())
        assert v["sources"] == {"template": len(insights)}
        r = json.loads((d / "personalize" / "recaps" / f"{n}.json").read_text(encoding="utf-8"))
        assert r["recap_version"] == 1 and r["source"] == "template" and len(r["insight_ids"]) <= 5


def test_no_digit_or_number_word_outside_placeholders_for_every_kind_claim_lens_lang_club():
    claim_sets = [[], ["match_max"], ["first_goal"], ["equaliser"], ["go_ahead"], ["first_goal", "go_ahead"]]
    n = 0
    for (kind, sub), claims, lens, lang, club, team in product(KEYS, claim_sets, lenses.TEXT_LENSES, lenses.LANGS, lenses.CLUBS, ("home", "away")):
        for drop in (None, "xg"):  # also without xg (omitted when 0 or null)
            m = {k: v for k, v in METRICS[kind].items() if k != drop}
            c = synth(0, kind, sub, team, claims, metrics=m)
            title, text = templates.template(c, NAMES, lens, lang, club)
            for s in (title, text):
                assert P.validate_text(s, m, claims, lang) == [], (kind, sub, claims, lens, lang, club, s)
                assert not re.search(r"<\w+>", s)
                P.resolve_text(s, m, lang=lang)
            n += 1
    assert n > 1000


def test_plural_correctness_for_value_one_and_many():
    one = synth(0, "lines_broken", "goal")
    two = synth(1, "lines_broken", "goal", metrics={**METRICS["lines_broken"], "lines_broken": M(2, "lines"), "passes": M(3, "passes")})
    for lang, a, b in (("en", "1 line in 1 pass", "2 lines in 3 passes"), ("es", "1 línea en 1 pase", "2 líneas en 3 pases")):
        assert a in P.resolve_text(templates.template(one, NAMES, "analyst", lang, "neutral")[1], one["metrics"], lang=lang)
        assert b in P.resolve_text(templates.template(two, NAMES, "analyst", lang, "neutral")[1], two["metrics"], lang=lang)
    t = P.resolve_text(templates.template(one, NAMES, "fan", "en", "neutral")[0], one["metrics"])
    assert t == "Goal after breaking 1 line!" and "1 lines" not in t
    dom = synth(2, "momentum_shift", "dominance")
    assert "1 entry into" in P.resolve_text(templates.template(dom, NAMES, "analyst", "en", "neutral")[1], dom["metrics"])
    assert "1 entrada al" in P.resolve_text(templates.template(dom, NAMES, "analyst", "es", "neutral")[1], dom["metrics"], lang="es")


def test_plural_form_validation_rejects_digits_and_unknown_metric():
    m = {"n": M(1, "lines")}
    assert P.validate_text("{n} {n|line|lines}", m, [], "en") == []
    assert P.validate_text("{n} {n|line|2 lines}", m, [], "en")
    assert P.validate_text("{x|line|lines}", m, [], "en")
    assert P.resolve_text("{n|line|lines}", {"n": M(0, "lines")}) == "lines"


def test_spanish_uses_decimal_comma_and_english_a_point():
    g = synth(0, "goal_or_chance", "goal", claims=["first_goal"])
    es = P.resolve_text(templates.template(g, NAMES, "analyst", "es", "neutral")[1], g["metrics"], lang="es")
    en = P.resolve_text(templates.template(g, NAMES, "analyst", "en", "neutral")[1], g["metrics"], lang="en")
    assert "0,34 xG del motor" in es and "0.34 engine xG" in en
    assert P.fmt(M(9.7, "s"), "es") == "9,7" and P.fmt(M(9.7, "s")) == "9.7" and P.fmt(M(2, "lines"), "es") == "2"
    assert "Abrió el marcador" in es  # claim-backed wording


def test_perspective_own_vs_opponent_differ_and_neutral_names_both_teams():
    for (kind, sub), lens, lang in product(KEYS, lenses.TEXT_LENSES, lenses.LANGS):
        c = synth(0, kind, sub, "home")
        own, opp, neu = (templates.template(c, NAMES, lens, lang, club) for club in ("home", "away", "neutral"))
        assert own != opp and own != neu and opp != neu, (kind, sub, lens, lang)
    c = synth(0, "lines_broken", "goal", "home")
    assert NAMES["away"] in templates.template(c, NAMES, "analyst", "en", "neutral")[1] and NAMES["away"] not in templates.template(c, NAMES, "analyst", "en", "home")[1]
    assert lenses.perspective("home", "home") == "own" and lenses.perspective("home", "away") == "opponent" and lenses.perspective("neutral", "away") == "neutral"


def test_first_match_explains_the_concept_before_the_fact():
    c = synth(0, "pressure_spell", "shift_up")
    text = templates.template(c, NAMES, "first_match", "en", "neutral")[1]
    assert text.startswith(templates.CONCEPT["en"]["pressure_spell"] + " ") and text.count(". ") >= 1


def test_priority_clamps_and_bonuses():
    c = synth(0, "lines_broken", "goal", "home", importance=0.9)
    c["players"] = ["home-09"]
    assert lenses.priority(c) == 0.9 and lenses.priority(c, "away") == 0.9
    assert lenses.priority(c, "home") == 1.0 and lenses.priority(c, "home", "home-09") == 1.0
    c["importance"]["value"] = 0.5
    assert lenses.priority(c, "home", "home-09") == pytest.approx(0.9) and lenses.priority(c, "neutral", "home-09") == pytest.approx(0.75)
    assert lenses.main_metric(c) == "lines_broken" and lenses.main_metric(synth(1, "pressure_spell", "peak")) == "value" and lenses.main_metric(synth(2, "pressure_spell", "shift_up")) == "after"
    assert lenses.main_metric(synth(3, "goal_or_chance", "goal", metrics={})) is None


def test_recap_n0_has_empty_list_and_template_text():
    ins = [synth(0, "lines_broken", "goal", importance=0.1)]
    v = variants.build_variant(ins, "fan", "es", "neutral", NAMES)
    r = recaps.build_recap(ins, v, "fan", "es", "neutral")
    assert r["insight_ids"] == [] and r["text"] == recaps.NO_MOMENTS["es"] and r["source"] == "template" and recaps.picks(ins) == {}
    r = recaps.build_recap([], {"texts": {}}, "analyst", "en", "neutral")
    assert r["text"] == "No key moments in this clip"


def test_recap_picks_five_by_priority_ties_by_show_t_s_then_id():
    ins = [synth(i, "lines_broken", "shot", importance=0.7, show=float(50 - i)) for i in range(8)]  # equal priority: the earliest show_t_s win
    ins.append(synth(8, "lines_broken", "shot", importance=0.7, show=43.0))  # same show_t_s as i007: the id decides
    ins.append(synth(9, "lines_broken", "shot", importance=0.95, show=99.0))  # best priority, latest
    got = recaps.pick_moments(ins, "fan", "neutral")
    assert len(got) == 5 and "i009" in got and {"i007", "i008", "i006", "i005"} == set(got) - {"i009"}
    assert got == sorted(got, key=lambda i: next((d["show_t_s"], d["insight_id"]) for d in ins if d["insight_id"] == i))
    few = ins[:2]
    assert len(recaps.pick_moments(few, "fan", "neutral")) == 2  # min(5, n)
    away = [synth(0, "lines_broken", "shot", "away", importance=0.5)]
    assert recaps.pick_moments(away, "fan", "neutral") == [] and recaps.pick_moments(away, "fan", "away") == ["i000"]  # club bonus lifts it over the 0.6 threshold


def test_agent_text_is_validated_per_insight_and_falls_back():
    ins = [synth(0, "lines_broken", "goal"), synth(1, "lines_broken", "shot"), synth(2, "lines_broken", "lost")]
    ok = {"title": "Wow {lines_broken}", "text": "Nice {passes} {passes|pass|passes}"}
    got = {"i000": {l: ok for l in lenses.TEXT_LENSES}, "i001": {**{l: ok for l in lenses.TEXT_LENSES}, "fan": {"title": "Wow 3 lines", "text": "x"}},  # digit
           "ghost": {l: ok for l in lenses.TEXT_LENSES}}
    bodies, w = variants.valid_bodies(ins, got)
    v = variants.build_variant(ins, "fan", "en", "neutral", NAMES, bodies)
    assert [v["texts"][i]["source"] for i in ("i000", "i001", "i002")] == ["agent", "template", "template"] and v["sources"] == {"agent": 1, "template": 2}
    assert len(w) == 2 and any("ghost" in x for x in w) and any("i001" in x for x in w)
    assert variants.build_variant(ins, "analyst", "en", "neutral", NAMES, bodies)["sources"] == {"agent": 2, "template": 1}  # only the fan body of i001 was bad


def test_failing_agents_never_fail_the_job(tmp_path):
    d = tmp_path / "m"
    shutil.copytree(FIX, d)
    B.run(str(d), context={})
    boom = lambda *a: (_ for _ in ()).throw(RuntimeError("down"))
    w = build_personalize.run(str(d), lens_agent=boom, recap_agent=boom, translator=boom, context={})
    assert [x.split(" failed")[0] for x in w] == ["personalize: lens agent", "personalize: recap agent", "personalize: translator"] and all("down" in x for x in w)
    v = json.loads((d / "personalize" / "variants" / "fan_es_home.json").read_text(encoding="utf-8"))
    assert set(v["sources"]) == {"template"}


def test_recap_agent_placeholders_validated_and_stored_resolved():
    ins = [synth(0, "lines_broken", "goal", importance=0.9), synth(1, "pressure_spell", "peak", claims=["match_max"], importance=0.9, show=20.0)]
    v = variants.build_variant(ins, "fan", "en", "neutral", NAMES)
    picked = {"fan_neutral": ["i000", "i001"]}
    good = "Broke {i000.lines_broken} {i000.lines_broken|line|lines} with {i000.xg} xG."
    ok, w = recaps.valid_recaps(ins, picked, {"fan_neutral": good})
    r = recaps.build_recap(ins, v, "fan", "en", "neutral", ok["fan_neutral"])
    assert r["source"] == "agent" and r["text"] == "Broke 1 line with 0.34 xG." and w == []
    for bad in ("Broke 3 lines", "Broke {lines_broken}", "Broke {i001.nope}", "Broke two lines"):
        ok, w = recaps.valid_recaps(ins, picked, {"fan_neutral": bad})
        r = recaps.build_recap(ins, v, "fan", "en", "neutral", ok.get("fan_neutral"))
        assert r["source"] == "template" and len(w) == 1 and "{" not in r["text"]
    assert recaps.valid_recaps(ins, picked, {"fan_neutral": "It was the highest pressure of the match."})[0]  # backed by match_max
    ins2 = [synth(0, "lines_broken", "goal", importance=0.9)]
    assert not recaps.valid_recaps(ins2, {"fan_neutral": ["i000"]}, {"fan_neutral": "It was the highest pressure of the match."})[0]


def test_resolved_texts_of_the_fixture_goal(built):
    d, insights, _ = built
    goal = next(i for i in insights if i["kind"] == "goal_or_chance")
    v = json.loads((d / "personalize" / "variants" / "fan_es_home.json").read_text(encoding="utf-8"))["texts"][goal["insight_id"]]
    assert P.resolve_text(v["title"], goal["metrics"], lang="es") == "Muy bien: ¡Gol de Brackenford Athletic!"
    assert "0,34 xG del motor" in P.resolve_text(v["text"], goal["metrics"], lang="es")
