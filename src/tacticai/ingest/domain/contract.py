"""The match-package contract: vocabulary and the synthetic adapter's frame builder."""
from .clock import engine_time_s, match_time_s, SECOND_HALF_STEP
from .pitch import ENG_X, ENG_Y

ROLES = ("GK", "CB", "LB", "RB", "DM", "CM", "LM", "RM", "AM", "CF")  # engine e_PlayerRole order
STATES = ("open_play", "kick_off", "goal_kick", "free_kick", "corner", "throw_in", "penalty")  # engine game_mode order
TEAMS = ("home", "away")  # engine left, right


def player_id(side, i):
    return f"{side}-{i:02d}"


def team_of(pid):
    return pid.split("-")[0]


def make_row(obs, step, fi, engine_step):
    """Contract tracking frame from an engine observation. `step` = in-play row counter (drives clock_s only)."""
    b, bd = obs["ball"], obs["ball_direction"]
    players, yellow, red = [], [], []
    for side, t in zip(TEAMS, ("left", "right")):
        for i, (p, d) in enumerate(zip(obs[f"{t}_team"], obs[f"{t}_team_direction"])):
            players.append({"player_id": player_id(side, i), "x": round(p[0] * ENG_X, 3), "y": round(p[1] * ENG_Y, 3),
                            "vx": round(d[0] * ENG_X * 10, 2), "vy": round(d[1] * ENG_Y * 10, 2),
                            "role": ROLES[obs[f"{t}_team_roles"][i]], "on_pitch": obs[f"{t}_team_active"][i],
                            "observed": True, "confidence": 1.0})
            yellow += [player_id(side, i)] * (obs[f"{t}_team_yellow_card"][i] > 0)
            red += [player_id(side, i)] * (not obs[f"{t}_team_active"][i])
    o = obs["ball_owned_team"]
    return {"frame_index": fi, "t_s": engine_time_s(fi), "clock_s": match_time_s(step),
            "period": 2 if engine_step >= SECOND_HALF_STEP else 1, "camera": "main",
            "ball": {"x": round(b[0] * ENG_X, 3), "y": round(b[1] * ENG_Y, 3), "z": round(b[2], 3),
                     "vx": round(bd[0] * ENG_X * 10, 2), "vy": round(bd[1] * ENG_Y * 10, 2), "vz": round(bd[2] * 10, 2),
                     "observed": True, "confidence": 1.0},
            "players": players,
            "possession": {"team": TEAMS[o] if o >= 0 else None,
                           "player_id": player_id(TEAMS[o], obs["ball_owned_player"]) if o >= 0 else None},
            "game_state": STATES[obs["game_mode"]],
            "score": {"home": obs["score"][0], "away": obs["score"][1]},
            "cards": {"yellow": yellow, "red": red}}
