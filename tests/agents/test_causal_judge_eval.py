"""LIVE eval of the causal judge (real Foundry call). Run: TAI_LIVE=1 pytest tests/agents/test_causal_judge_eval.py -s"""
import os

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("TAI_LIVE") != "1", reason="live Foundry eval; set TAI_LIVE=1")

DATA = {"c1": {"events": [
    {"t_s": 10, "team": "home", "type": "counter_start"}, {"t_s": 14, "team": "home", "type": "shot", "xg": 0.2},
    {"t_s": 20, "team": "away", "type": "high_press_start"}, {"t_s": 24, "team": "away", "type": "long_ball"}, {"t_s": 3000, "team": "away", "type": "high_press"}]}}
BAD = {"bad1": "The home team's counter led to a goal.", "bad2": "The away team pressed high, which forced a long ball.",
       "bad3": "The home team's pressing produced the decisive big chance.", "bad4": "The away team pressed high in an attempt to win the ball back."}
GOOD = {"ok1": "The home team ran a counter that ended in a shot.", "ok2": "The away team pressed high during the second half.",
        "ok3": "The goal gave the home team the lead.", "ok4": "It matters because it came at a decisive stage of the match."}


def test_live_judge():
    from dotenv import load_dotenv
    load_dotenv(r"C:\Github\tacticAI\.env", override=True)
    from tacticai.agents import causal_judge
    r = causal_judge.judge([{"id": i, "text": t} for i, t in {**BAD, **GOOD}.items()], DATA)
    print("rejected:", r)
    assert set(r) == set(BAD), r
