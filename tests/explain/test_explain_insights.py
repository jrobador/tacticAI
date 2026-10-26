import json
import os
import shutil
from pathlib import Path

import pytest

from tacticai.explain.application import build_insights as B
from tacticai.explain.domain import importance, moments, placeholders as P

FIX = Path(__file__).parent / "fixtures" / "match"
REAL = Path(__file__).resolve().parents[2] / "data" / "matches" / "20261023-235553-f205"


def jl(name):
    return [json.loads(l) for l in (FIX / "interpret" / name).read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture
def match(tmp_path):
    d = tmp_path / "m"
    shutil.copytree(FIX, d)
    return str(d)


@pytest.fixture
def insights(match):
    return B.build_insights(match)


def by(insights, kind, subtype=None):
    return [i for i in insights if i["kind"] == kind and (subtype is None or i["subtype"] == subtype)]


def test_lines_broken_adapter_cites_only_real_fields(insights):
    lb = by(insights, "lines_broken", "goal")[0]
    assert set(lb["metrics"]) == {"lines_broken", "passes", "duration_s", "xg"}
    assert lb["players"] == ["home-10", "home-06", "home-09"]  # sequences.jsonl sequence 3
    assert lb["refs"]["note_index"] == 1 and lb["refs"]["sequence_ids"] == [3]
    assert all(set(m) == {"value", "unit"} for i in insights for m in i["metrics"].values())
    away = by(insights, "lines_broken", "end_of_period")[0]
    assert "xg" not in away["metrics"]  # xg 0 is omitted


def test_show_t_s_of_goal_play_is_the_goal(insights):
    lb = by(insights, "lines_broken", "goal")[0]
    assert (lb["t_s"], lb["until_t_s"], lb["show_t_s"]) == (13.5, 24.3, 24.3)
    notes = jl("tactical_notes.jsonl")
    for i in insights:
        if i["refs"]["note_index"] is not None and i["kind"] != "goal_or_chance":
            assert i["show_t_s"] >= notes[i["refs"]["note_index"]]["until_t_s"]


def test_goal_shot_association_and_absorption(insights):
    g = by(insights, "goal_or_chance", "goal")[0]
    assert (g["t_s"], g["until_t_s"], g["show_t_s"]) == (21.0, 24.3, 24.3)
    assert g["refs"] == {"note_index": 5, "sequence_ids": [3], "event_indices": [6, 7], "candidate_id": None}
    assert g["players"] == ["home-09"] and g["metrics"]["xg"]["value"] == 0.335
    assert g["importance"]["factors"]["value"] > 0
    assert g["claims"] == ["first_goal", "go_ahead"]
    assert not by(insights, "goal_or_chance", "chance_scored")  # the big_chance note was absorbed


def test_goal_without_shot_still_generates_insight_and_value_one():
    events = [{"type": "goal", "team": "away", "t_s": 5.0, "clock_s": 50.0, "period": 1, "scorer_id": "away-09", "sequence_id": None, "score_before": {"home": 0, "away": 0}}]
    c = moments.detect([], [], events)
    assert len(c) == 1 and c[0]["refs"]["event_indices"] == [0] and c[0]["metrics"] == {} and (c[0]["t_s"], c[0]["until_t_s"]) == (5.0, 5.0)
    imp = importance.rate(c, events, True)[0]
    assert imp["factors"]["value"] == 1.0
    assert importance.rate(c, events, False)[0]["factors"]["value"] is None


def test_unabsorbed_big_chance_is_an_insight():
    note = {"t_s": 3.0, "until_t_s": 3.0, "start_clock_s": 30.0, "period": 1, "team": "home", "kind": "big_chance", "text_key": "big_chance_missed",
            "evidence": {"event_indices": [0], "frame_index": 30, "xg": 0.3, "player_id": "home-09"}, "strength": 0.3}
    events = [{"type": "shot", "team": "home", "t_s": 3.0, "outcome": "no_goal", "xg": 0.3, "score_before": {"home": 0, "away": 0}}]
    c = moments.detect([note], [], events)
    assert [(x["kind"], x["subtype"], x["players"], x["show_t_s"]) for x in c] == [("goal_or_chance", "chance_missed", ["home-09"], 3.0)]


def test_importance_ranges_and_rounding(insights):
    for i in insights:
        f = i["importance"]["factors"]
        assert set(f) == {"rarity", "value", "score_context", "minute"}
        for v in list(f.values()) + [i["importance"]["value"]]:
            assert 0 <= v <= 1 and v == round(v, 3)
    ids = [i["insight_id"] for i in insights]
    assert ids == [f"i{k:03d}" for k in range(len(ids))]
    assert [i["show_t_s"] for i in insights] == sorted(i["show_t_s"] for i in insights)


def test_importance_without_vaep_and_minute_and_score_context(insights):
    events = jl("events_enriched.jsonl")
    cands = moments.detect(jl("tactical_notes.jsonl"), jl("sequences.jsonl"), events)
    imps = importance.rate(cands, events, False)
    assert all(i["factors"]["value"] is None for i in imps)
    k = next(n for n, c in enumerate(cands) if c["kind"] == "lines_broken" and c["subtype"] == "goal")
    f = imps[k]["factors"]
    assert imps[k]["value"] == round((f["rarity"] + f["score_context"] + f["minute"]) / 3, 3)
    c = dict(cands[k], clock_s=88 * 60 + 400, score_before={"home": 0, "away": 3})
    late = importance.rate([c], events, False)[0]["factors"]
    assert late["minute"] == 1.0 and late["score_context"] == 0.5


def test_interception_vaep_goes_to_the_opponent():
    ev = [{"type": "pass", "team": "home", "t_s": 1.0, "vaep": {"total": -0.1}, "vaep_interception": {"total": 0.3}},
          {"type": "shot", "team": "away", "t_s": 2.0, "vaep": {"total": 0.2}}]
    assert importance.team_vaep(ev, "away", 0, 3) == pytest.approx(0.5)
    assert importance.team_vaep(ev, "home", 0, 3) == pytest.approx(-0.1)


def test_equaliser_late_beats_same_goal_three_nil_down():
    def goal(before):
        return [{"type": "goal", "team": "home", "t_s": 5.0, "clock_s": 5280.0, "period": 2, "scorer_id": "home-09", "sequence_id": None, "score_before": before}]
    a, b = goal({"home": 0, "away": 3}), goal({"home": 3, "away": 3})
    ia = importance.rate(moments.detect([], [], a), a, False)[0]["value"]
    ib = importance.rate(moments.detect([], [], b), b, False)[0]["value"]
    assert ib > ia
    assert moments.detect([], [], goal({"home": 2, "away": 3}))[0]["claims"] == ["equaliser"]
    assert moments.detect([], [], goal({"home": 1, "away": 1}))[0]["claims"] == ["go_ahead"]


def test_momentum_gated_but_adapters_work(insights):
    assert moments.MOMENTUM_REVIEWED is False
    assert not by(insights, "momentum_shift")
    swing = {"t_s": 11.7, "until_t_s": 14.8, "start_clock_s": 176.9, "period": 1, "team": "home", "kind": "momentum_swing", "text_key": "momentum_to_home",
             "evidence": {"timeline_windows": [6, 7], "metric": "momentum", "values": [-0.066, 0.378]}, "strength": 0.4438}
    s = moments.momentum_insight(swing, 0, jl("events_enriched.jsonl"))
    assert s["subtype"] == "swing" and s["metrics"] == {"before": {"value": -0.066, "unit": "momentum"}, "after": {"value": 0.378, "unit": "momentum"}}
    dom = jl("tactical_notes.jsonl")[2]
    d = moments.momentum_insight(dom, 2, jl("events_enriched.jsonl"))
    assert d["subtype"] == "dominance" and d["metrics"]["xg"] == {"value": 0.335, "unit": "engine xG"} and d["metrics"]["final_third_entries"]["value"] == 0
    away = moments.momentum_insight(jl("tactical_notes.jsonl")[3], 3, [])
    assert away["metrics"]["before"]["value"] == 0.491 and away["metrics"]["after"]["value"] == -0.677  # mean_before / mean_after preferred


def test_pressure_claims_and_subtypes(insights):
    subs = {(i["subtype"], i["team"]) for i in by(insights, "pressure_spell")}
    assert subs == {("peak", "home"), ("peak", "away"), ("shift_down", "home")}
    assert all(i["claims"] == (["match_max"] if i["subtype"] == "peak" else []) for i in by(insights, "pressure_spell"))


def test_agent_context_from_agents_json(match):
    agents = {"agents_version": 1, "tactical": {"key_notes": [{"note_index": 5, "rank": 1, "text": "goal"}, {"note_index": 1, "rank": 2, "text": "move"}],
                                                "phases": [{"candidate_id": 0, "rank": 1, "text": "counter", "evidence": []}]}}
    plain = B.build_insights(match)
    Path(match, "interpret", "agents.json").write_text(json.dumps(agents), encoding="utf-8")
    ins = B.build_insights(match)
    g = by(ins, "goal_or_chance")[0]
    assert g["agent_context"] == [{"ref": "key_note", "note_index": 5, "rank": 1, "text": "goal"}]  # phase 13.5-18.5 ends before the goal shot at 21.0
    lb = by(ins, "lines_broken", "goal")[0]
    assert [c["ref"] for c in lb["agent_context"]] == ["key_note", "phase"] and lb["refs"]["candidate_id"] == 0
    away = by(ins, "lines_broken", "end_of_period")[0]
    assert away["agent_context"] == []
    assert [i["importance"] for i in plain] == [i["importance"] for i in ins]


def test_stub_gives_templates_and_writes_files(match):
    ins, warns = B.run(match, context={})
    assert warns == [] and all(i["text"]["source"] == "template" for i in ins)
    lines = [json.loads(l) for l in Path(match, "explain", "insights.jsonl").read_text(encoding="utf-8").splitlines()]
    assert lines == ins
    meta = json.loads(Path(match, "explain", "meta.json").read_text(encoding="utf-8"))
    assert meta["text_sources"] == {"template": len(ins)} and meta["momentum_reviewed"] is False
    assert not [f for f in os.listdir(Path(match, "explain")) if f.endswith(".tmp")]
    for i in ins:
        assert P.validate_text(i["text"]["fact"], i["metrics"], i["claims"], "en") == []
        assert P.validate_text(i["text"]["why"], i["metrics"], i["claims"], "en") == []
    lb = by(ins, "lines_broken", "goal")[0]
    assert P.resolve_text(lb["text"]["fact"], lb["metrics"]) == "Brackenford Athletic broke 2 lines in 2 passes"


def test_explainer_wrapper_validates_per_insight(match):
    ids = [i["insight_id"] for i in B.build_insights(match)]
    out = {ids[0]: {"fact": "ok {value}", "why": "fine"}, ids[1]: {"fact": "bad 5", "why": "x"}, "i999": {"fact": "a", "why": "b"}}
    ins, warns = B.run(match, agent=lambda i, c: out, context={})
    assert ins[0]["text"]["source"] == "agent" and ins[1]["text"]["source"] == "template"
    assert any("i999" in w for w in warns) and any(ids[1] in w for w in warns)
    def boom(i, c):
        raise RuntimeError("down")
    ins, warns = B.run(match, agent=boom, context={})
    assert all(i["text"]["source"] == "template" for i in ins) and "down" in warns[0]


@pytest.mark.skipif(not (REAL / "tracking.jsonl").exists(), reason="needs data/matches")
def test_match_context_real(tmp_path):
    ctx = B.build_match_context(str(REAL))
    assert ctx["teams"]["home"]["name"] == "Brackenford Athletic" and ctx["roster"]["home-09"]["team"] == "home"
    assert "projection" in ctx and "results" in ctx


def test_placeholders():
    m = {"xg": {"value": 0.3354, "unit": "engine xG"}, "lines_broken": {"value": 2, "unit": "lines"}, "duration_s": {"value": 9.74, "unit": "s"}}
    v = lambda t, c=(), lang="en": P.validate_text(t, m, list(c), lang)
    assert v("Broke {lines_broken} lines in {duration_s}") == []
    assert v("Broke 2 lines") and v("Broke {lines_broken} lines in {passes}")
    assert v("It scored two goals") and v("Marcó dos goles", lang="es") and not v("Marcó un gol y una chance", lang="es") and not v("Hit a shot, an effort")
    assert v("The highest pressure") and v("The highest pressure", ["match_max"]) == []
    assert v("It was the first goal") and v("Es el pico del partido", lang="es") and v("Es el pico del partido", ["match_max"], "es") == []
    assert v("stray { brace}")
    assert P.resolve_text("{lines_broken} / {duration_s} / {xg}", m) == "2 / 9.7 / 0.34"
    assert P.validate_text("{i003.xg}", {}, [], "en", {"i003": m}) == [] and P.resolve_text("{i003.xg}", {}, {"i003": m}) == "0.34"
    with pytest.raises(KeyError):
        P.resolve_text("{nope}", m)
