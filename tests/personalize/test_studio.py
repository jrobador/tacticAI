from tacticai.personalize.application import fan, studio
from tacticai.personalize.domain import fan_facts

from test_fan import GOAL, META, ROSTER  # sibling test module (rootdir-relative import, as pytest collects it)


def ctx_facts():
    facts = fan_facts.detect(GOAL, [], ROSTER)
    return facts, fan.Ctx(facts, ROSTER, META)


def writer(texts):
    calls = []

    def write(brief, lang, revise=None):
        calls.append(revise)
        return {"opening": "What a game, {home_short} {home_goals}–{away_goals} {away_short}.",
                "segments": [{"fact_id": "f01", "text": texts[len(calls) - 1]}], "closing": "Over to you."}
    write.calls = calls
    return write


def test_script_links_each_segment_to_its_play_and_fills_numbers():
    facts, ctx = ctx_facts()
    out, w = studio.write_script(facts, ctx, "en", writer(["Corlune scores, set up by Quennick."]), lambda items, brief, voice: {})
    assert w == [] and out["source"] == "agent" and out["opening"] == "What a game, BKA 1–0 WXC."
    assert [(s["fact_id"], s["kind"], s["t_s"]) for s in out["segments"]] == [("f01", "goal", 2.5)]


def test_rejected_script_is_revised_once_then_falls_back_to_data():
    facts, ctx = ctx_facts()
    w1 = writer(["Corlune, the shooter, scores.", "Corlune scores, set up by Quennick."])
    judge = lambda items, brief, voice: {"f01": "'the shooter': role read out"} if any("shooter" in i["text"] for i in items) else {}
    out, w = studio.write_script(facts, ctx, "en", w1, judge)
    assert len(w1.calls) == 2 and out["source"] == "agent" and out["segments"][0]["text"] == "Corlune scores, set up by Quennick."
    w2 = writer(["Corlune, the shooter, scores.", "Corlune, the shooter, again."])
    out, w = studio.write_script(facts, ctx, "en", w2, judge)
    # only the rejected part is replaced: the opening stays the agent's, the segment falls back to the goal's data line
    assert out["source"] == "mixed" and any("f01 rejected twice" in x for x in w)
    assert out["opening"] == "What a game, BKA 1–0 WXC." and [s["kind"] for s in out["segments"]] == ["goal"]
    assert out["segments"][0]["text"].startswith("Goal · Corlune")
