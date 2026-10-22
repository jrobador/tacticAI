from tacticai.ingest.domain.evaluate import evaluate, interest_score, meets, rank_value
from tacticai.ingest.domain.recipe import example_recipes

ROSTER = {"players": [{"player_id": "home-00", "name": "Alpha"}, {"player_id": "home-01", "name": "Beta"},
                      {"player_id": "away-00", "name": "Gamma"}]}


def ev(typ, team="home", t=0, scorer=None):
    return {"type": typ, "team": team, "clock_s": t, "scorer_id": scorer}


def test_ends_in_shot_goal():
    assert meets(["ends_in_shot"], [ev("shot")], ROSTER) == (True, [])
    assert meets(["ends_in_shot"], [ev("goal")], ROSTER)[0]
    assert meets(["ends_in_shot"], [ev("pass")], ROSTER) == (False, ["ends_in_shot"])
    assert meets(["ends_in_goal"], [ev("shot")], ROSTER) == (False, ["ends_in_goal"])
    assert meets(["ends_in_goal"], [ev("goal")], ROSTER)[0]


def test_goal_by_and_team():
    g = [ev("goal", "away", scorer="away-00")]
    assert meets(["goal_by:gamma"], g, ROSTER)[0] and meets(["goal_by:GAMMA"], g, ROSTER)[0]
    assert not meets(["goal_by:Alpha"], g, ROSTER)[0]  # Alpha is home-00, not away
    assert not meets(["goal_by:Gamma"], [ev("goal", "away")], ROSTER)[0]
    assert not meets(["goal_by:Gamma"], [ev("shot", "away", scorer="away-00")], ROSTER)[0]
    assert meets(["goal_by_team:away"], g, ROSTER)[0] and not meets(["goal_by_team:home"], g, ROSTER)[0]
    assert meets(["goal_by_team:home"], [ev("goal", "home")], ROSTER)[0]


def test_ranking_always_met_and_missing_list():
    assert meets(["more_pressure:home", "more_possession:away"], [], ROSTER) == (True, [])
    assert meets(["ends_in_goal", "more_pressure:home", "ends_in_shot"], [], ROSTER) == (False, ["ends_in_goal", "ends_in_shot"])


def test_rank_value():
    rows = [{"possession": {"team": "home"}}] * 3 + [{"possession": {"team": "away"}}]
    assert rank_value(["ends_in_shot"], rows, []) == 0.0
    assert rank_value(["more_possession:home"], rows, []) == 0.75
    assert rank_value(["more_pressure:home"], [], []) == 0.0  # None counts as 0


def test_interest_comeback_late_lead_changes():
    # away scores, home equalises, home scores late: away led, then home leads
    s, r = interest_score([ev("goal", "away", 100), ev("goal", "home", 2000), ev("goal", "home", 5000), ev("shot", "home", 10), ev("shot", "away", 20)])
    assert r == {"goals": 3, "comeback": True, "late_goals": 1, "lead_changes": 1, "shots": 2}
    assert s == 9 + 5 + 3 + 2 + 0.4
    # no comeback: leader never behind, draw then same side leads again is not a change
    s, r = interest_score([ev("goal", "home", 1), ev("goal", "away", 2), ev("goal", "home", 3)])
    assert r["comeback"] is False and r["lead_changes"] == 0 and s == 9
    # behind and finishing level counts as comeback; 0-0 has nothing
    assert interest_score([ev("goal", "away", 1), ev("goal", "home", 2)])[1]["comeback"] is True
    assert interest_score([ev("pass")]) == (0, {"goals": 0, "comeback": False, "late_goals": 0, "lead_changes": 0, "shots": 0})
    # unordered input is sorted by time: away 2-0 up, home levels and overtakes 3-2
    assert interest_score([ev("goal", "home", 9), ev("goal", "away", 1), ev("goal", "home", 7), ev("goal", "away", 2), ev("goal", "home", 8)])[1]["lead_changes"] == 1


def test_evaluate_modes():
    full, sit, _ = example_recipes()
    assert evaluate(sit, [], [ev("shot")], ROSTER) == {"ok": True, "missing": [], "score": 0.0, "reasons": {}}
    out = evaluate(full, [], [ev("goal", "home", 1)], ROSTER)
    assert out["ok"] and out["score"] == 3 and out["reasons"]["goals"] == 1
