import pytest

from tacticai.ingest.domain.recipe import RecipeError, example_recipes, from_dict, to_dict, validate


def test_examples_roundtrip():
    for r in example_recipes():
        assert validate(r) == []
        assert from_dict(to_dict(r)) == r
        assert to_dict(from_dict(to_dict(r))) == to_dict(r)


def _side(n=11, gks=1):
    return [[-1.0 if i < gks else -0.2, 0.0, "GK" if i < gks else "CM"] for i in range(n)]


def _sit(**kw):
    s = {"start": "x", "ends_when": "goal", "wanted": []}
    s.update(kw)
    return {"mode": "situation", "situation": s}


def errs(d):
    with pytest.raises(RecipeError) as e:
        from_dict(d)
    return "; ".join(e.value.messages)


def test_invalid():
    assert "unknown formation" in errs({"mode": "full_match", "home": {"formation": "9-9-9"}})
    assert "exactly one GK" in errs(_sit(positions={"home": _side(gks=2), "away": _side()}))
    assert "exactly 11" in errs(_sit(positions={"home": _side(10), "away": _side()}))
    assert "ball outside" in errs(_sit(ball=[2.0, 0.0]))
    assert "bad predicate" in errs(_sit(wanted=["goal_by_team:both"]))
    assert "situation is required" in errs({"mode": "situation"})
    assert "situation is required" in errs({"mode": "full_match", "situation": {}})


def test_collects_all_problems():
    e = errs({"mode": "full_match", "home": {"style": "zzz", "level": 2}, "seeds": 0, "steps": 5000})
    assert all(s in e for s in ("style", "level", "seeds", "steps"))


def test_valid_predicates():
    d = _sit(wanted=["ends_in_shot", "ends_in_goal", "goal_by:Mossvane", "goal_by_team:home",
                     "more_pressure:away", "more_possession:home"])
    assert from_dict(d).situation.wanted[2] == "goal_by:Mossvane"

