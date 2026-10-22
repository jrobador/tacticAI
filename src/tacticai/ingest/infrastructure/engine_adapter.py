"""Everything that touches the engine module `_tai_engine` (only available inside the engine Docker image)."""
import numpy as np

W, H = 1280, 720
PHYSICS_STEPS_PER_FRAME = 10


def _r6(v):
    return round(float(v), 6)


def _observe(info):
    """Engine info -> plain dict, in tracking-row key order (without the clock and pitch-derived fields)."""
    d = {"in_play": bool(info.is_in_play), "engine_step": int(info.step),
         "ball": [_r6(info.ball_position[i]) for i in range(3)],
         "ball_direction": [_r6(info.ball_direction[i]) for i in range(3)],
         "ball_owned_team": int(info.ball_owned_team), "ball_owned_player": int(info.ball_owned_player)}
    for t in ("left", "right"):
        ps = list(getattr(info, f"{t}_team"))
        d[f"{t}_team"] = [[_r6(p.position[0]), _r6(p.position[1])] for p in ps]
        d[f"{t}_team_direction"] = [[_r6(p.direction[0]), _r6(p.direction[1])] for p in ps]
        d[f"{t}_team_roles"] = [int(p.role) for p in ps]
        d[f"{t}_team_tired_factor"] = [_r6(p.tired_factor) for p in ps]
        d[f"{t}_team_yellow_card"] = [int(p.has_card) for p in ps]
        d[f"{t}_team_active"] = [bool(p.is_active) for p in ps]
    d["score"] = [int(info.left_goals), int(info.right_goals)]
    d["game_mode"] = int(info.game_mode)
    return d


class EngineMatch:
    def __init__(self, seed, left, right, total_steps, second_half_step):
        """left/right: lists of (x, y, role name) from domain.formations.build_team."""
        import _tai_engine as e  # imported here so host-side code works without the engine
        self.env = env = e.GameEnv()
        gc = env.game_config
        gc.physics_steps_per_frame, gc.render_resolution_x, gc.render_resolution_y, gc.render = \
            PHYSICS_STEPS_PER_FRAME, W, H, True
        sc = e.ScenarioConfig.make()
        sc.game_duration = total_steps
        sc.second_half = second_half_step
        sc.left_team_difficulty = sc.right_team_difficulty = 1.0
        sc.deterministic = False
        sc.game_engine_random_seed = seed
        sc.reverse_team_processing = bool(seed % 2)
        sc.left_agents = sc.right_agents = 0
        for team, players in ((sc.left_team, left), (sc.right_team, right)):
            for x, y, role in players:
                team.append(e.FormationEntry(x, y, getattr(e.e_PlayerRole, f"e_PlayerRole_{role}"), False, True))
        env.start_game()
        env.state = e.GameState.game_running
        env.reset(sc, True)

    def step(self):
        """Advance one engine frame -> (observation dict, BGR frame bytes)."""
        env = self.env
        env.step()
        info = env.get_info()
        fr = np.frombuffer(env.get_frame(), np.uint8).reshape(W, H, 3)
        rgb = np.concatenate([fr[:, :, 0], fr[:, :, 1], fr[:, :, 2]]).reshape(3, H, W).transpose(1, 2, 0)[::-1]
        return _observe(info), np.ascontiguousarray(rgb[:, :, ::-1]).tobytes()
