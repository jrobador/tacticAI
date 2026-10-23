import json
import math

from tacticai.interpret.application.train_models import DERIVED, load_xpass

ROW = {"length_m": 14.0, "progressive_m": 6.0, "start_x_att": 10.0, "passer_pressure": 0.5, "opponents_near_line": 1,
       "nearest_opponent_to_receiver_m": 3.0, "lines_broken": 1}


def test_xpass_computes_derived_features_from_plain_row():
    f = load_xpass("src/tacticai/interpret/models/xpass_v1.json")
    assert set(DERIVED) <= set(f.info["features"]) and not set(DERIVED) & set(ROW)
    assert 0 < f(ROW) < 1
    assert f({**ROW, "nearest_opponent_to_receiver_m": None}) != f(ROW)  # null -> train mean, then derived
    assert math.isclose(DERIVED["length_sq_100"][1](ROW), 1.96)
