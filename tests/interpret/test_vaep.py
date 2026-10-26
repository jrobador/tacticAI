import json
import random

from tacticai.interpret.application.models import load_vaep
from tacticai.training.train_models import train_vaep
from tacticai.interpret.domain import vaep

SB = {"home": 0, "away": 0}


def ev(type, t, team, player, x, y, period=1, **kw):
    return dict(type=type, t_s=t, period=period, team=team, player_id=player, x=x, y=y, score_before=SB, **kw)


def passe(t, team, player, x, y, ex, ey, outcome="complete", by=None, period=1):
    return ev("pass", t, team, player, x, y, period, end_x=ex, end_y=ey, outcome=outcome, intercepted_by=by)


def toy(f):  # P(scores) grows with a0_xa, shots are worth a lot; concedes constant
    return (0.9 if f["a0_shot"] else 0.1 + 0.001 * (f["a0_xa"] + 54)), 0.05


def test_actions_interception_credited_to_interceptor_at_end_point():
    acts = vaep.build_actions([passe(1, "home", "h1", 0, 0, 20, 5, "intercepted", by="a3"), ev("tackle", 2, "away", "a4", 10, 1)])
    assert [(a["type"], a["team"], a["player_id"]) for a in acts] == [("pass", "home", "h1"), ("interception", "away", "a3"), ("tackle", "away", "a4")]
    assert not acts[0]["success"] and (acts[1]["x"], acts[1]["y"]) == (20, 5)
    f = vaep.features(acts, 1)  # a_i is away: coordinates flipped, a_{i-1} (the pass) is the other team
    assert f["a0_interception"] == 1 and f["a0_xa"] == -20 and f["a0_ya"] == -5 and f["a1_same_team"] == 0 and f["a1_pass"] == 1


def test_labels_within_10_actions_and_not_across_period_end():
    evs = [passe(i, "home", "h1", 0, 0, 5, 0) for i in range(14)]
    evs.insert(12, ev("goal", 11.5, "home", "h1", 50, 0))  # after action 11 (0-based)
    acts = vaep.build_actions(evs)
    lab = vaep.labels(acts)
    assert acts[11]["goals_after"] == ["home"] and acts[12]["goals_after"] == []
    assert lab[11] == (True, False) and lab[1] == (True, False)  # 1 + 10 reaches action 11
    assert lab[0] == (False, False)  # 0 + 10 does not
    assert lab[12] == (False, False)


def test_label_does_not_cross_period_change():
    evs = [passe(1, "home", "h1", 0, 0, 5, 0), passe(2, "home", "h1", 0, 0, 5, 0, period=2), ev("goal", 3, "home", "h1", 50, 0, period=2)]
    acts = vaep.build_actions(evs)
    assert vaep.labels(acts) == [(False, False), (True, False)]
    assert acts[1]["reset"]


def test_value_flip_on_possession_change_and_reset_after_goal():
    evs = [passe(1, "home", "h1", 0, 0, 30, 0), passe(2, "away", "a1", 0, 0, 5, 0), ev("goal", 3, "home", "h1", 50, 0),
           passe(4, "home", "h1", 0, 0, 5, 0)]
    acts = vaep.build_actions(evs)
    model = lambda f: (0.3, 0.2)
    v = vaep.action_values(acts, model)
    assert v[0]["offensive"] == 0.3 and v[0]["defensive"] == -0.2  # first action: previous state is 0
    assert abs(v[1]["offensive"] - (0.3 - 0.2)) < 1e-12 and abs(v[1]["defensive"] + (0.2 - 0.3)) < 1e-12  # flipped previous state
    assert v[2]["offensive"] == 0.3  # reset after the goal


def test_goal_action_has_positive_offensive():
    evs = [passe(1, "home", "h1", 0, 0, 40, 0), ev("shot", 2, "home", "h2", 45, 0, end_x=54.4, end_y=1, outcome="goal", xg=0.4), ev("goal", 2.1, "home", "h2", 54, 1)]
    acts = vaep.build_actions(evs)
    v = vaep.action_values(acts, toy)
    assert acts[1]["success"] and v[1]["offensive"] > 0 and abs(v[1]["total"] - (v[1]["offensive"] + v[1]["defensive"])) < 1e-12


def test_rating_shape_gk_and_missing_model():
    evs = [passe(1, "home", "h1", 0, 0, 40, 0), ev("shot", 2, "home", "h1", 45, 0, end_x=54.4, end_y=1, outcome="goal")]
    acts = vaep.build_actions(evs)
    vals = vaep.action_values(acts, toy)
    r = vaep.vaep_rating("h1", "CM", acts, vals)
    assert set(r) == {"value", "unit", "scope", "breakdown", "reason"} and r["unit"] == "goals_added" and r["scope"] == "full_match" and r["reason"] is None
    assert r["value"] == round(sum(v["total"] for v in vals), 3) and [b["item"] for b in r["breakdown"]] == ["pass", "shot"]
    assert set(r["breakdown"][0]) == {"item", "count", "offensive", "defensive", "points"}
    assert vaep.vaep_rating("h1", "GK", acts, vals)["value"] is None and vaep.vaep_rating("h1", "GK", acts, vals)["reason"] == "saves_not_validated"
    miss = vaep.vaep_rating("h1", "CM", acts, None)
    assert miss["value"] is None and miss["reason"] == "vaep_model_missing" and miss["breakdown"] == []


def test_train_vaep_writes_loadable_model(tmp_path):
    rng = random.Random(0)
    rows = []
    for seed in range(1, 61):
        for _ in range(60):
            f = {n: rng.random() for n in vaep.FEATURES}
            rows.append({**f, "type": "pass", "job_seed": seed, "scores": int(f["a0_xa"] > 0.7 and rng.random() < 0.8), "concedes": int(rng.random() < 0.05)})
    d = tmp_path / "actions_v1"
    d.mkdir()
    (d / "actions.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    out = tmp_path / "vaep.json"
    m = train_vaep(str(d), str(out))
    assert m["scores"]["metrics"]["test"]["auc"] > m["scores"]["metrics"]["baseline"]["auc"] - 0.2 and "beats_baseline" in m["concedes"]
    saved = json.loads(out.read_text())
    for heads, expect_model in (((True, True), True), ((True, False), False), ((False, True), False)):
        saved["scores"]["beats_baseline"], saved["concedes"]["beats_baseline"] = heads
        out.write_text(json.dumps(saved))
        f = load_vaep(str(out))
        assert (f is not None) == expect_model
    saved["scores"]["beats_baseline"] = saved["concedes"]["beats_baseline"] = True
    out.write_text(json.dumps(saved))
    f = load_vaep(str(out))
    ps, pc = f(rows[0])
    assert 0 < ps < 1 and 0 < pc < 1 and f.info["id"] == "vaep_v1"


def test_goal_after_interception_is_not_recorded_on_the_pass():
    acts = vaep.build_actions([passe(1, "home", "h1", 0, 0, 20, 5, "intercepted", by="a3"), ev("goal", 2, "away", "a3", 50, 0)])
    assert [a["type"] for a in acts] == ["pass", "interception"]
    assert acts[0]["goals_after"] == [] and acts[1]["goals_after"] == ["away"]
    assert acts[0]["goals_after"] is not acts[1]["goals_after"]


def test_rating_points_equal_offensive_plus_defensive_after_rounding():
    acts = vaep.build_actions([passe(1, "home", "h1", 0, 0, 5, 0), passe(2, "home", "h1", 0, 0, 5, 0)])
    vals = [{"offensive": 0.0114, "defensive": -0.0116, "total": -0.0002}, {"offensive": 0.0001, "defensive": 0.0, "total": 0.0001}]
    r = vaep.vaep_rating("h1", "CM", acts, vals)
    b = r["breakdown"][0]
    assert (b["offensive"], b["defensive"], b["points"]) == (0.011, -0.012, -0.001) and r["value"] == -0.001
