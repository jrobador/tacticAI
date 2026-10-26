import pytest

from tacticai.ingest.application.recipe_config import recipe_config
from tacticai.ingest.domain.recipe import MAX_Y, ROLES, RecipeError, example_recipes, from_dict, validate
from tacticai.ingest.domain.situations import TEMPLATES, resolve


@pytest.mark.parametrize("name", TEMPLATES)
def test_template_shape(name):
    t = TEMPLATES[name]
    for side in ("attack", "defend"):
        pl = t[side]
        assert len(pl) == 11 and [p[2] for p in pl].count("GK") == 1
        assert all(p[2] in ROLES and abs(p[0]) <= 1 and abs(p[1]) <= MAX_Y for p in pl)
    assert abs(t["ball"][0]) <= 1 and abs(t["ball"][1]) <= MAX_Y
    r = from_dict({"mode": "situation", "situation": {"template": name, "ball_owner": "home"}})
    assert validate(r) == []


def test_resolve_owner_mirrors_and_copies():
    pos, ball = resolve("counter", "home")
    pos2, ball2 = resolve("counter", "away")
    assert pos["home"] == pos2["away"] and pos["away"] == pos2["home"]
    assert ball2 == [-ball[0], -ball[1]]
    pos["home"][0][0] = 99
    assert TEMPLATES["counter"]["attack"][0][0] == -1.0


def test_wing_left_is_y_mirror():
    r, l = TEMPLATES["wing_attack_right"], TEMPLATES["wing_attack_left"]
    swap = {"LB": "RB", "RB": "LB", "LM": "RM", "RM": "LM"}
    for side in ("attack", "defend"):
        assert [[x, -y, swap.get(role, role)] for x, y, role in r[side]] == [[x, y, role] for x, y, role in l[side]]
    assert l["ball"] == [r["ball"][0], -r["ball"][1]]


def _err(**kw):
    with pytest.raises(RecipeError) as e:
        from_dict({"mode": "situation", "situation": kw})
    return str(e.value)


def test_template_validation():
    pl = [[-1.0, 0, "GK"]] + [[-0.2, 0, "CM"]] * 10
    assert "excludes positions and ball" in _err(template="counter", ball_owner="home", positions={"home": pl, "away": pl})
    assert "excludes positions and ball" in _err(template="counter", ball_owner="home", ball=[0, 0])
    assert "unknown template" in _err(template="nope", ball_owner="home")
    assert "template needs ball_owner" in _err(template="counter")


def test_recipe_config_uses_template():
    r = example_recipes()[2]
    k = recipe_config(r, 0)["kwargs"]
    assert k["left"] == TEMPLATES["counter"]["attack"] and k["right"] == TEMPLATES["counter"]["defend"]
    assert k["ball"] == TEMPLATES["counter"]["ball"]
    r.situation.ball_owner = "away"
    k = recipe_config(r, 0)["kwargs"]
    assert k["right"] == TEMPLATES["counter"]["attack"] and k["ball"] == [0.13, -0.02]
