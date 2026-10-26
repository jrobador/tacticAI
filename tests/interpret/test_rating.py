import json
import os

from test_analysis_package import make

from tacticai.interpret.application.analyze_match import analyze


def toy(f):  # scoring chance grows with a0_xa, shots are worth a lot; concedes constant
    return (0.9 if f["a0_shot"] else 0.1 + 0.001 * (f["a0_xa"] + 54)), 0.05


toy.info = {"id": "toy_vaep"}
ICPT = dict(type="pass", frame_index=35, t_s=3.5, clock_s=63.5, period=1, team="home", player_id="home-01", x=30.0, y=0.0, to_player_id=None, end_x=40.0, end_y=0.0,
            outcome="intercepted", intercepted_by="away-01")


def run(tmp_path, model):
    out = analyze(make(tmp_path, [ICPT]), vaep_model=model)
    load = lambda n: json.load(open(os.path.join(out, n)))
    return load("meta.json"), [json.loads(l) for l in open(os.path.join(out, "events_enriched.jsonl"))], {p["player_id"]: p["rating"] for p in load("players.json")["players"]}


def test_without_model_rating_is_null_not_zero(tmp_path):
    meta, evs, rt = run(tmp_path, None)
    assert meta["models"]["vaep"] is None and not any("vaep" in e or "vaep_interception" in e for e in evs)
    assert rt["home-01"]["value"] is None and rt["home-01"]["reason"] == "vaep_model_missing" and rt["home-01"]["unit"] == "goals_added"


def test_with_model_writes_vaep_and_goals_added_rating(tmp_path):
    meta, evs, rt = run(tmp_path, toy)
    assert meta["models"]["vaep"] == {"id": "toy_vaep"}
    acts = [e for e in evs if e["type"] in ("pass", "tackle", "shot")]
    assert all(set(e["vaep"]) == {"offensive", "defensive", "total"} for e in acts)
    icpt = next(e for e in evs if e.get("outcome") == "intercepted")
    assert set(icpt["vaep_interception"]) == {"offensive", "defensive", "total"} and all("vaep_interception" not in e for e in evs if e is not icpt)
    home = rt["home-01"]
    assert home["unit"] == "goals_added" and home["scope"] == "full_match" and home["reason"] is None
    assert home["value"] == round(sum(e["vaep"]["total"] for e in acts if e["player_id"] == "home-01"), 3)
    assert [b["item"] for b in home["breakdown"]] == ["pass", "shot"] and rt["away-01"]["breakdown"][0]["item"] in ("interception", "tackle")
    assert rt["home-00"] == {"value": None, "unit": "goals_added", "scope": "full_match", "breakdown": [], "reason": "saves_not_validated"}
