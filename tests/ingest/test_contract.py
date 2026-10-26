from tacticai.ingest.application.generate_match import make_meta
from tacticai.ingest.domain.contract import make_row


def obs(**kw):
    """Hand-made engine observation: 2 players per team (GK + one more), ball owned by right player 1."""
    o = {"ball": [0.5, -0.1, 0.25], "ball_direction": [0.01, 0.02, 0.1], "ball_owned_team": 1, "ball_owned_player": 1,
         "left_team": [[-1.0, 0.0], [0.2, 0.1]], "left_team_direction": [[0.0, 0.0], [0.01, -0.01]],
         "left_team_roles": [0, 9], "left_team_yellow_card": [0, 1], "left_team_active": [True, True],
         "right_team": [[1.0, 0.0], [0.3, -0.1]], "right_team_direction": [[0.0, 0.0], [-0.02, 0.0]],
         "right_team_roles": [0, 2], "right_team_yellow_card": [0, 0], "right_team_active": [True, False],
         "score": [1, 2], "game_mode": 4}
    return o | kw


def test_contract_frame():
    r = make_row(obs(), 7, 12, 1600)
    assert (r["frame_index"], r["t_s"], r["clock_s"], r["period"], r["camera"]) == (12, 1.2, 12.64, 2, "main")
    assert r["ball"] == {"x": 27.2, "y": -8.36, "z": 0.25, "vx": 5.44, "vy": 16.72, "vz": 1.0,
                         "observed": True, "confidence": 1.0}
    assert [p["player_id"] for p in r["players"]] == ["home-00", "home-01", "away-00", "away-01"]
    assert r["players"][1] == {"player_id": "home-01", "x": 10.88, "y": 8.36, "vx": 5.44, "vy": -8.36, "role": "CF",
                               "on_pitch": True, "observed": True, "confidence": 1.0}
    assert (r["players"][3]["role"], r["players"][3]["on_pitch"], r["players"][3]["vx"]) == ("LB", False, -10.88)
    assert r["possession"] == {"team": "away", "player_id": "away-01"}
    assert (r["game_state"], r["score"]) == ("corner", {"home": 1, "away": 2})
    assert r["cards"] == {"yellow": ["home-01"], "red": ["away-01"]}
    assert make_row(obs(ball_owned_team=-1, ball_owned_player=-1), 0, 0, 0)["possession"] == {"team": None, "player_id": None}


def test_meta_projection_and_calibration():
    m = make_meta("m", 1, "4-3-3", "4-4-2", "home", 10, 10, None, {})
    assert m["projection"] == {"applies": True, "effective_play_s": 3300}
    assert m["calibration"] == {"physical_absolute": False}
