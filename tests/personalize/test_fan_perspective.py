from tacticai.personalize.domain import fan_perspective as V

KINDS = ["goal", "miss", "save", "mistake", "pinned", "turn", "move", "pass", "carry", "tackle", "sprint"]


def test_every_kind_has_a_stance_for_each_side_and_each_stance_a_meaning():
    for kind in KINDS:
        for punished in (True, False):
            f = {"kind": kind, "team": "home", "punished": punished}
            ours, theirs = V.stance(f, "home"), V.stance(f, "away")
            assert ours != theirs, kind  # the two supporters never feel the same about one fact
            assert {ours, theirs} <= set(V.MEANING) and V.stance(f, "neutral") == "thrill"


def test_goal_is_joy_for_one_side_and_pain_for_the_other():
    goal = {"kind": "goal", "team": "away"}
    assert (V.stance(goal, "away"), V.stance(goal, "home")) == ("celebrate", "suffer")
    assert V.stance({"kind": "mistake", "team": "home", "punished": True}, "home") == "blame_ours"


def test_result_and_roles():
    assert (V.result("home", "home"), V.result("home", "away"), V.result(None, "away"), V.result("home", "neutral")) == ("win", "loss", "draw", "decided")
    save = {"kind": "save", "team": "home", "players": {"shooter": "home-09", "keeper": "away-00"}}
    assert V.player_roles(save, {"home-09": "home", "away-00": "away"}) == [{"player_id": "home-09", "role": "shooter", "side": "home"},
                                                                             {"player_id": "away-00", "role": "keeper", "side": "away"}]
