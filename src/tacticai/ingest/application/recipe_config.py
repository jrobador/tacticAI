"""Pure mapping: Recipe + seed -> EngineMatch kwargs (no engine needed)."""
from ..domain import situations
from ..domain.formations import CATALOG, kickoff_positions, shape_vector
from ..domain.styles import tactics_for

ONE_METRE = 1 / 54.4  # observation x units per metre
SITUATION_STEPS = 300


def _ball_in_front(owner, positions):
    """1 m in front of the owner's most advanced outfield player, in absolute coordinates.
    Positions are team-relative (right team = point reflection of left)."""
    sign = 1 if owner == "home" else -1
    x, y, _ = max((p for p in positions[owner] if p[2] != "GK"), key=lambda p: p[0])
    return [sign * (x + ONE_METRE), sign * y]


def recipe_config(recipe, seed, steps=None):
    """Returns {"steps", "kwargs"}: kwargs for EngineMatch (plus total_steps/second_half_step)."""
    kick = "left" if seed % 2 == 0 else "right"
    sit = recipe.situation
    tball = None
    if sit and sit.template:
        pos, tball = situations.resolve(sit.template, sit.ball_owner)
    elif sit and sit.positions:
        pos = {s: [list(p) for p in sit.positions[s]] for s in ("home", "away")}
    else:
        pos = {"home": kickoff_positions(CATALOG[recipe.home.formation], kick == "left"),
               "away": kickoff_positions(CATALOG[recipe.away.formation], kick == "right")}
    steps = steps or recipe.steps
    kw = dict(left=pos["home"], right=pos["away"],
              left_tactics=tactics_for(recipe.home.style), right_tactics=tactics_for(recipe.away.style),
              left_shape=shape_vector(recipe.home.formation), right_shape=shape_vector(recipe.away.formation),
              difficulty=(recipe.home.level, recipe.away.level))
    if recipe.mode == "full_match":
        kw.update(total_steps=3000, second_half_step=1500)
    else:
        ball = tball or sit.ball
        if ball is None and sit.ball_owner:
            ball = _ball_in_front(sit.ball_owner, pos)
        kw.update(total_steps=steps, second_half_step=999999999, ball=ball)
    end_on = sit.ends_when if sit and sit.ends_when != "steps" else None
    return {"steps": steps, "end_on": end_on, "kwargs": kw}


class EndWatch:
    """The engine ignores end_episode_on_*, so the loop checks the observation itself.
    Call update(obs) per frame (obs has in_play, engine_step, score, game_mode, ball_owned_team); True = stop."""

    def __init__(self, end_on):
        self.end_on, self.score, self.owner = end_on, None, -1

    def update(self, obs):
        if not self.end_on or obs["engine_step"] < 0:  # engine_step -1 = start-up frames
            return False
        if self.score is None:
            self.score = obs["score"]
        o = obs["ball_owned_team"]
        changed = o in (0, 1) and self.owner in (0, 1) and o != self.owner
        if o in (0, 1):
            self.owner = o
        return {"goal": obs["score"] != self.score,
                "possession_change": changed,
                "out_of_play": not obs["in_play"] or obs["game_mode"] != 0}[self.end_on]
