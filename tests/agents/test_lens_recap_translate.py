"""Offline tests of the batched Lens, Recap and Translator: fakes replace the Foundry calls."""
import json
import shutil
from itertools import product
from pathlib import Path

import pytest

from tacticai.explain.application import build_insights as B
from tacticai.personalize.application import build_personalize, recaps
from tacticai.personalize.domain import lenses, templates

FIX = Path(__file__).resolve().parents[1] / "explain" / "fixtures" / "match"
NAMES = {"home": "Brackenford Athletic", "away": "Wexmoor City"}
LENS_BODY = {"title": "A notable moment", "text": "Something happened here."}
XG_BODY = {"title": "A shot", "text": "A shot worth {xg} engine xG."}


@pytest.fixture
def match(tmp_path):
    d = tmp_path / "m"
    shutil.copytree(FIX, d)
    B.run(str(d), context={})
    return d


def read(d, kind, name):
    return json.loads((d / "personalize" / kind / f"{name}.json").read_text(encoding="utf-8"))


def lens_fake(insights, ctx):
    return {i["insight_id"]: {l: XG_BODY if i["insight_id"] == "i003" else LENS_BODY for l in lenses.TEXT_LENSES} for i in insights}


def recap_fake(insights, picks, ctx):
    return {k: "A quiet spell, then {i002.lines_broken} {i002.lines_broken|line|lines}." for k in picks}


def translator_fake(texts, ctx):
    out = {}
    for k, t in texts.items():
        out[k] = ("Una pausa, luego {i002.lines_broken} {i002.lines_broken|línea|líneas}." if k.startswith("recap.")
                  else "Un disparo de {xg} xG del motor." if k.startswith("i003.") and k.endswith(".text") else "Un momento destacado" if k.endswith(".title") else "Algo pasó aquí.")
    return out


def test_perspective_function_equals_template_for_the_templates_own_body():
    c = {"insight_id": "i000", "kind": "pressure_spell", "subtype": "peak", "team": "home", "metrics": {"value": 1, "match_mean": 1}, "claims": ["match_max"]}
    for kind_sub, lens, lang, club, team in product([("lines_broken", "goal"), ("pressure_spell", "shift_down"), ("goal_or_chance", "chance_missed"), ("momentum_shift", "swing")],
                                                    lenses.TEXT_LENSES, lenses.LANGS, lenses.CLUBS, ("home", "away")):
        c = {**c, "kind": kind_sub[0], "subtype": kind_sub[1], "team": team, "metrics": {"xg": 1}}
        body = templates.neutral_body(c, NAMES, lens, lang, lenses.perspective(club, team))
        assert templates.perspective_text(c, *body, lens, lang, club) == templates.template(c, NAMES, lens, lang, club)
    t = templates.perspective_text(c, "T", "X.", "first_match", "en", "neutral")
    assert t == ("T", templates.CONCEPT["en"][c["kind"]] + " X.")


def test_lens_body_with_a_digit_falls_back_only_for_that_insight(match):
    def fake(insights, ctx):
        got = lens_fake(insights, ctx)
        got["i002"]["fan"] = {"title": "Wow 3 lines", "text": "x"}
        return got
    w = build_personalize.run(str(match), lens_agent=fake, recap_agent=recap_fake, translator=translator_fake, context={})
    assert len([x for x in w if "i002 fan agent text rejected" in x]) == 1 and not [x for x in w if "failed" in x]
    v = read(match, "variants", "fan_en_home")["texts"]
    assert v["i002"]["source"] == "template" and v["i001"]["source"] == "agent" and v["i003"]["source"] == "agent"
    assert v["i001"]["title"] == templates.PREFIX["en"]["fan"]["opponent"]["good"] + LENS_BODY["title"]  # the side is added by the code
    assert read(match, "variants", "analyst_en_home")["texts"]["i002"]["source"] == "agent"
    assert read(match, "variants", "first_match_en_neutral")["texts"]["i001"]["text"].startswith(templates.CONCEPT["en"]["pressure_spell"] + " " + LENS_BODY["text"])


def test_translation_missing_a_placeholder_falls_back_to_the_spanish_template(match):
    def tr(texts, ctx):
        out = translator_fake(texts, ctx)
        out["i003.fan.text"] = "Un disparo muy peligroso."  # no {xg}
        return out
    w = build_personalize.run(str(match), lens_agent=lens_fake, recap_agent=recap_fake, translator=tr, context={})
    assert any("i003 fan translation rejected" in x and "placeholders" in x for x in w)
    es = read(match, "variants", "fan_es_home")["texts"]
    assert es["i003"]["source"] == "template" and es["i001"]["source"] == "agent"
    assert read(match, "variants", "analyst_es_home")["texts"]["i003"]["source"] == "agent"
    assert es["i001"]["title"].endswith("Un momento destacado")
    assert read(match, "variants", "fan_en_home")["texts"]["i003"]["source"] == "agent"


def test_recap_with_empty_picks_never_calls_the_fake(match):
    ins = [json.loads(l) for l in (match / "explain" / "insights.jsonl").read_text(encoding="utf-8").splitlines()]
    for i in ins:
        i["importance"]["value"] = 0.05
    (match / "explain" / "insights.jsonl").write_text("\n".join(json.dumps(i) for i in ins), encoding="utf-8")
    calls = []
    build_personalize.run(str(match), lens_agent=lens_fake, recap_agent=lambda *a: calls.append(a), translator=translator_fake, context={})
    assert calls == []
    r = read(match, "recaps", "fan_en_home")
    assert r["insight_ids"] == [] and r["text"] == recaps.NO_MOMENTS["en"] and r["source"] == "template"
    assert read(match, "recaps", "fan_es_home")["text"] == recaps.NO_MOMENTS["es"]


def test_recaps_agent_gets_only_combinations_with_moments(match):
    seen = {}
    build_personalize.run(str(match), recap_agent=lambda i, picks, c: seen.update(picks) or recap_fake(i, picks, c), context={})
    assert set(seen) == set(recaps.picks([json.loads(l) for l in (match / "explain" / "insights.jsonl").read_text(encoding="utf-8").splitlines()]))


def test_spanish_recap_fallback_uses_spanish_titles_and_agent_recap_is_resolved(match):
    def tr(texts, ctx):
        out = translator_fake(texts, ctx)
        out.pop("recap.fan_home")
        return out
    w = build_personalize.run(str(match), recap_agent=recap_fake, translator=tr, context={})  # no Lens: the Spanish titles are the templates
    assert any("recap fan_home translation rejected" in x for x in w)
    es, en = read(match, "recaps", "fan_es_home"), read(match, "recaps", "fan_en_home")
    assert es["source"] == "template" and "romper" in es["text"] and "Goal after" not in es["text"] and "{" not in es["text"]
    assert en["source"] == "agent" and en["text"] == "A quiet spell, then 2 lines."
    ok = read(match, "recaps", "fan_es_neutral")
    assert ok["source"] == "agent" and ok["text"] == "Una pausa, luego 2 líneas."


def test_whole_translation_failure_gives_one_warning_and_spanish_templates(match):
    def boom(texts, ctx):
        raise RuntimeError("timeout")
    w = build_personalize.run(str(match), lens_agent=lens_fake, recap_agent=recap_fake, translator=boom, context={})
    assert [x for x in w if "translator failed" in x] and len(w) == 1
    assert set(read(match, "variants", "fan_es_home")["sources"]) == {"template"} and read(match, "recaps", "fan_es_home")["source"] == "template"
    assert read(match, "variants", "fan_en_home")["sources"] == {"agent": 6}


def test_no_foundry_means_silent_templates(match):
    assert build_personalize.run(str(match), context={}) == []
    assert read(match, "variants", "fan_es_home")["sources"] == {"template": 6}
    assert read(match, "recaps", "fan_en_home")["source"] == "template"


def test_same_placeholders_distinguishes_selector_from_value():
    from tacticai.personalize.application.translator_agent import same_placeholders as same
    en = "{passes} {passes|pass|passes}"
    assert same(en, "{passes} {passes|pase|pases}")
    assert not same(en, "{passes} {passes}")
    assert not same("{xg}", "{xg|a|b}")
