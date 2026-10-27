import json
import shutil
from pathlib import Path

from tacticai.personalize.application import fan
from tacticai.personalize.domain import fan_facts

FIX = Path(__file__).resolve().parents[1] / "explain" / "fixtures" / "match"
ROSTER = [{"player_id": "home-00", "name": "Venmere", "team": "home", "role": "GK"}, {"player_id": "home-09", "name": "Corlune", "team": "home", "role": "ST"},
          {"player_id": "home-08", "name": "Quennick", "team": "home", "role": "CM"}, {"player_id": "away-00", "name": "Calbrook", "team": "away", "role": "GK"},
          {"player_id": "away-04", "name": "Kestrane", "team": "away", "role": "CB"}]
META = {"teams": {"home": {"name": "Brackenford Athletic", "short": "BKA"}, "away": {"name": "Wexmoor City", "short": "WXC"}}}
CLEAR = fan_facts.clear_chance_xg()


def ev(t, type_, team, pid, **kw):
    return {"t_s": t, "clock_s": 60 + t, "type": type_, "team": team, "player_id": pid, "score_before": {"home": 0, "away": 0}, **kw}


def test_clear_chance_cut_comes_from_the_xg_model():
    m = json.loads((Path(fan_facts._MODELS) / "xg_v1.json").read_text(encoding="utf-8"))["metrics"]["test"]
    assert CLEAR == m["goals"] / m["n"]


def test_goal_with_assist_save_and_clear_miss():
    events = [ev(1, "pass", "home", "home-08", outcome="complete", to_player_id="home-09"),
              ev(2, "shot", "home", "home-09", outcome="goal", xg=0.4, dist_goal_center_m=20),
              ev(2.5, "goal", "home", "home-09", scorer_id="home-09"),
              ev(5, "shot", "away", "away-04", outcome="no_goal", on_target=True, xg=0.05),
              ev(8, "shot", "home", "home-09", outcome="no_goal", on_target=False, xg=CLEAR + 0.05),
              ev(9, "shot", "home", "home-08", outcome="no_goal", on_target=False, xg=CLEAR - 0.05)]
    d = fan_facts.detect(events, [], ROSTER)
    kinds = [(f["kind"], f["team"], f["tier"]) for f in d["facts"]]
    # nothing is filtered out: the pass, the goal, the save and both misses, the weak one too
    assert kinds == [("pass", "home", "reaction"), ("goal", "home", "moment"), ("save", "away", "moment"), ("miss", "home", "moment"), ("miss", "home", "moment")]
    goal = d["facts"][1]
    assert goal["players"] == {"scorer": "home-09", "assist": "home-08"} and goal["where"] == "outside_box" and goal["claims"] == ["first_goal", "go_ahead"]
    assert d["facts"][2]["players"]["keeper"] == "home-00"
    assert (d["facts"][3]["clear_chance"], d["facts"][4]["clear_chance"]) == (True, False)
    assert d["verdict"]["winner"] == "home" and d["verdict"]["deserved"] and d["verdict"]["figure"] == "home-09"


def test_every_lost_ball_is_a_fact_and_says_what_followed():
    lost = ev(1, "pass", "home", "home-08", outcome="intercepted", intercepted_by="away-04")
    shot_after = fan_facts.detect([lost, ev(3, "shot", "away", "away-04", outcome="no_goal", xg=0.1)], [], ROSTER)["facts"][0]
    back_first = fan_facts.detect([lost, ev(2, "pass", "home", "home-09", outcome="complete"), ev(3, "shot", "away", "away-04", outcome="no_goal", xg=0.1)], [], ROSTER)["facts"][0]
    assert (shot_after["kind"], shot_after["threat"], shot_after["punished"]) == ("mistake", True, False)
    assert (back_first["kind"], back_first["threat"]) == ("mistake", False)


def test_tackle_carries_the_run_into_it_from_the_tracking():
    rows = [{"t_s": t / 10, "players": [{"player_id": "home-08", "x": t * 0.7, "y": 0.0, "vx": 7.0, "vy": 0.0}]} for t in range(0, 31)]
    d = fan_facts.detect([ev(3, "tackle", "home", "home-08", from_player_id="away-04")], [], ROSTER, rows=rows)
    (t,) = d["facts"]
    assert t["kind"] == "tackle" and t["players"] == {"winner": "home-08", "loser": "away-04"}
    assert (t["metrics"]["run_m"]["value"], t["metrics"]["run_kmh"]["value"]) == (14, 25)  # 2 s at 7 m/s


def test_pass_details_move_sprint_and_awards():
    # 0.8 ** 5 = 0.33: the xPass model gave the move less than an even chance, so it is an olé
    passes = [ev(t, "pass", "home", "home-08", outcome="complete", sequence_id=1, lines_broken=2 if t == 2 else 0, to_player_id="home-09", xpass=0.8)
              for t in (1, 2, 3, 4, 5)]
    seqs = [{"sequence_id": 1, "team": "home", "passes": 5, "players": ["home-08", "home-09"], "end_t_s": 6, "start_clock_s": 61},
            {"sequence_id": 2, "team": "away", "passes": 1, "players": ["away-04"], "end_t_s": 9, "start_clock_s": 69},
            {"sequence_id": 3, "team": "home", "passes": 1, "players": ["home-09"], "end_t_s": 12, "start_clock_s": 72}]
    sprints = [{"player_id": "home-09", "t_s": 20, "clock_s": 80, "top_speed_m_s": 8.0, "distance_m": 15.4}]
    stats = [{"player_id": "home-09", "team": "home", "physical": {"distance_m": 120.4, "top_speed_m_s": 8.0, "sprints": 2},
              "passing": {"completed": 0}, "shooting": {"max_shot_speed_m_s": None}}]
    d = fan_facts.detect(passes, [], ROSTER, seqs, sprints, stats)
    assert [(f["kind"], f["t_s"]) for f in d["facts"]] == [("pass", 1), ("pass", 2), ("pass", 3), ("pass", 4), ("pass", 5), ("move", 5), ("sprint", 20)]
    assert [f["splits_block"] for f in d["facts"][:5]] == [False, True, False, False, False]
    assert d["facts"][-1]["metrics"]["top_kmh"]["value"] == 29
    assert [(a["award"], a["metrics"]) for a in d["awards"]] == [("engine", {"distance_m": {"value": 120, "unit": "count"}}),
                                                                   ("fastest", {"top_kmh": {"value": 29, "unit": "count"}}), ("sprinter", {"sprints": {"value": 2, "unit": "count"}})]


def test_check_is_the_pipeline_contract_digits_names_and_claims():
    metrics = {"minute": {"value": 3, "unit": "count"}}
    names = ["Corlune", "Quennick", "Brackenford Athletic", "Wexmoor City"]
    ok = lambda t, claims=(): fan.check(t, metrics, list(claims), "en", ["Corlune", "Brackenford Athletic"], names, META)
    assert ok("Corlune scores in minute {minute} for {home_short}!") == []
    assert ok("Corlune scores in minute 3!")
    assert ok("Quennick sets up Corlune")
    assert ok("Corlune opens the scoring: first goal!")
    assert ok("Corlune, first goal!", ["first_goal"]) == []


GOAL = [ev(1, "pass", "home", "home-08", outcome="complete", to_player_id="home-09"),
        ev(2, "shot", "home", "home-09", outcome="goal", xg=0.4), ev(2.5, "goal", "home", "home-09", scorer_id="home-09")]


def fake_writer(stance_of=None):
    """Writes every slot of the brief (the score where the item has it); `stance_of` overrides the stance it claims for a moment."""
    calls = []
    text = lambda m: "Corlune! {home_short} {home_goals}–{away_goals} {away_short}" if "{home_goals}" in m["placeholders"] else "Corlune!"

    def write(brief, lang, revise=None):
        calls.append(revise)
        if revise:
            return {"moments": {r["id"][2:]: {"stance": next(m["stance"] for m in brief["moments"] if m["fact_id"] == r["id"][2:]), "title": "Fixed", "text": text(next(m for m in brief["moments"] if m["fact_id"] == r["id"][2:]))}
                                for r in revise if r["id"].startswith("m:")}}
        return {"moments": {m["fact_id"]: {"stance": (stance_of or {}).get(m["fact_id"], m["stance"]), "title": "GOAL! Corlune", "text": text(m)} for m in brief["moments"]},
                "verdict": {"headline": "Full time!", "text": "{home_short} {home_goals}–{away_goals} {away_short}"},
                "ratings": {r["player_id"]: f"{r['name']} was there" for r in brief["ratings"]}, "awards": {},
                "player_lines": {(p["player_id"], p["fact_id"]): f"{p['name']}!" for p in brief["player_lines"]},
                "ask_examples": ["Who scored?", "Who passed?", "Who shot?"]}
    write.calls = calls
    return write


def test_brief_gives_each_club_its_own_stance_for_the_same_goal():
    ctx = fan.Ctx(fan_facts.detect(GOAL, [], ROSTER), ROSTER, META)
    stance = lambda club: next(s["brief"]["stance"] for s in fan.slots(ctx, "en", club) if s["id"] == "m:f01")
    assert (stance("home"), stance("away"), stance("neutral")) == ("celebrate", "suffer", "thrill")
    reader = fan.brief(ctx, "en", "away", fan.slots(ctx, "en", "away"))["reader"]
    assert reader == "a supporter of Wexmoor City (WXC)"


def test_view_keeps_judged_text_and_player_lines():
    ctx = fan.Ctx(fan_facts.detect(GOAL, [], ROSTER), ROSTER, META)
    view, w = fan.write_view(ctx, "en", "home", write=fake_writer(), judge=lambda items, brief: {})
    assert w == [] and [m["source"] for m in view["moments"]] == ["agent", "agent"] and [m["stance"] for m in view["moments"]] == ["enjoy", "celebrate"]
    assert view["moments"][1]["text"] == "Corlune! BKA 1–0 WXC"
    assert view["player_lines"] == {"home-08": {"f00": "Quennick!", "f01": "Quennick!"}, "home-09": {"f00": "Corlune!", "f01": "Corlune!"}}
    assert view["ask_examples"] == ["Who scored?", "Who passed?", "Who shot?"] and view["card_s"] == fan_facts.CARD_S


def test_wrong_stance_is_revised_once_and_a_second_rejection_falls_back():
    ctx = fan.Ctx(fan_facts.detect(GOAL, [], ROSTER), ROSTER, META)
    # The WXC reader must suffer BKA's goal; the writer celebrates it, the revision fixes it.
    w1 = fake_writer(stance_of={"f01": "celebrate"})
    view, w = fan.write_view(ctx, "en", "away", write=w1, judge=lambda items, brief: {})
    assert len(w1.calls) == 2 and view["moments"][1]["title"] == "Fixed" and view["moments"][1]["stance"] == "suffer"
    # The judge rejects the moment every time: one revision, then the fallback line of data.
    w2 = fake_writer()
    view, w = fan.write_view(ctx, "en", "away", write=w2, judge=lambda items, brief: {"m:f01": "'GOAL!': cheers their scorer"})
    assert len(w2.calls) == 2 and view["moments"][1]["source"] == "fallback"
    assert (view["moments"][1]["title"], view["moments"][1]["text"]) == ("Goal", "Corlune · Quennick · BKA 1–0 WXC")
    assert any("m:f01 rejected twice" in x for x in w)


def test_run_writes_facts_and_six_views_from_fallbacks_without_foundry(tmp_path):
    d = tmp_path / "m"
    shutil.copytree(FIX, d)
    warnings = fan.run(str(d))
    out = d / "personalize" / "fan"
    assert (out / "facts.json").exists() and len(list(out.glob("*_*.json"))) == 6
    view = json.loads((out / "es_home.json").read_text(encoding="utf-8"))
    assert view["sources"]["agent"] == 0 and warnings == []
