from tacticai.ingest.application.recipe_config import ONE_METRE, EndWatch, recipe_config
from tacticai.ingest.domain.recipe import example_recipes
from tacticai.ingest.domain.styles import tactics_for


def test_full_match_mapping():
    full = example_recipes()[0]
    c = recipe_config(full, 4)
    k = c["kwargs"]
    assert c["steps"] == 3000 and k["total_steps"] == 3000 and k["second_half_step"] == 1500
    assert len(k["left_shape"]) == len(k["right_shape"]) == 22
    assert k["left_tactics"] == tactics_for("possession") and k["right_tactics"] == tactics_for("counter")
    assert k["difficulty"] == (1.0, 0.8)
    assert max(p[0] for p in k["left"]) == 0.0 and max(p[0] for p in k["right"]) <= -0.1  # even seed: left kicks off
    assert max(p[0] for p in recipe_config(full, 5)["kwargs"]["right"]) == 0.0


def test_situation_ball_owner_and_end():
    sit = example_recipes()[1]
    k = recipe_config(sit, 0)["kwargs"]
    assert k["ball"] == [-0.3, 0.2] and recipe_config(sit, 0)["end_on"] == "possession_change" and k["total_steps"] == 300
    sit.situation.ball = None
    ball = recipe_config(sit, 0)["kwargs"]["ball"]
    best = max(p[0] for p in recipe_config(sit, 0)["kwargs"]["left"] if p[2] != "GK")
    assert abs(ball[0] - (best + ONE_METRE)) < 1e-9
    sit.situation.ball_owner = "away"
    best = max(p[0] for p in recipe_config(sit, 0)["kwargs"]["right"] if p[2] != "GK")
    assert abs(recipe_config(sit, 0)["kwargs"]["ball"][0] - (-best - ONE_METRE)) < 1e-9
    sit.situation.ends_when = "steps"
    assert recipe_config(sit, 0, steps=50)["end_on"] is None
    assert recipe_config(sit, 0, steps=50)["steps"] == 50


def _o(step=5, in_play=True, score=(0, 0), mode=0, owner=-1):
    return {"engine_step": step, "in_play": in_play, "score": list(score), "game_mode": mode, "ball_owned_team": owner}


def test_end_watch():
    w = EndWatch("possession_change")
    assert [w.update(_o(owner=o)) for o in (0, -1, 0, -1, 1)] == [False, False, False, False, True]
    w = EndWatch("goal")
    assert [w.update(_o(score=s)) for s in ((0, 0), (0, 0), (1, 0))] == [False, False, True]
    w = EndWatch("out_of_play")
    assert not w.update(_o(step=-1, in_play=False)) and not w.update(_o()) and w.update(_o(in_play=False))
    assert not EndWatch(None).update(_o(in_play=False))
