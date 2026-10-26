import pytest

from tacticai.agents import foundry
from tacticai.ingest.application import scenario_agent as sa
from tacticai.ingest.application.catalog import check_recipe


def _out():
    team = sa._Team(formation="4-3-3", style="counter", level=1.0)
    situation = sa._Situation(start="counter", ball_owner="away", ends_when="possession_change",
                              wanted=["goal_by_team:away"], template="counter")
    return sa.ScenarioOutput(recipe=sa._Recipe(mode="situation", home=team, away=team, situation=situation,
                                               seeds=200, steps=300, seed=0), summary="Wexmoor counter.")


def test_not_configured_is_not_implemented(monkeypatch):
    monkeypatch.setattr(foundry, "configured", lambda: False)
    with pytest.raises(NotImplementedError):
        sa.draft_recipe("a counter")


def test_configured_returns_plain_valid_dict(monkeypatch):
    monkeypatch.setattr(foundry, "configured", lambda: True)
    seen = {}
    monkeypatch.setattr(foundry, "run", lambda *a, **k: seen.update(k) or _out())
    out = sa.draft_recipe("Wexmoor counter that ends in a goal")
    assert out["summary"] == "Wexmoor counter." and seen["max_output_tokens"] == 800
    assert None not in out["recipe"]["situation"].values() and check_recipe(out["recipe"]) == []
