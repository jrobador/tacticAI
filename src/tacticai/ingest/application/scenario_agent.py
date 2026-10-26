"""Scenario Agent: request text (+ current recipe) -> recipe and summary. One Foundry call, no tools."""
import json
from typing import Literal

from pydantic import BaseModel

from ...agents import foundry
from ..domain import recipe as recipe_mod
from ..domain.formations import CATALOG
from ..domain.situations import TEMPLATES
from ..domain.styles import STYLES
from .catalog import catalog

TIMEOUT_S = 15


class _Team(BaseModel):
    formation: Literal[tuple(CATALOG)]
    style: Literal[tuple(STYLES)]
    level: float


class _Situation(BaseModel):
    start: str
    ball_owner: Literal["home", "away"] | None
    ends_when: Literal[recipe_mod.ENDS]
    wanted: list[str]
    template: Literal[tuple(TEMPLATES)] | None


class _Recipe(BaseModel):
    mode: Literal["full_match", "situation"]
    home: _Team
    away: _Team
    situation: _Situation | None
    seeds: int
    steps: int
    seed: int | None


class ScenarioOutput(BaseModel):
    recipe: _Recipe
    summary: str


RULES = """You turn a football scenario request into a match recipe for a simulator, and you edit the current recipe when one is given.
Teams: home = Brackenford Athletic (BKA), away = Wexmoor City (WXC). "Wexmoor attacks" means ball_owner away.
Use only the catalog below. Never invent options.

Rules:
- mode is full_match or situation. `situation` is required for mode situation and must be null for full_match.
- A template (situation.template) needs ball_owner and excludes positions and ball. ball_owner is who STARTS attacking, not who scores.
- level is between 0.7 and 1.0 (default 1.0). Never change steps or seed unless asked: steps is 300 for situations and 3000 for full_match; a new recipe has seed 0.
- seeds is 1..200: about 50 when the request asks for a shot, about 200 when it asks for a goal, 1 or a few otherwise.
- situation.start is a short description. ends_when is one of the catalog values ("possession_change" if the request does not say otherwise).
- wanted filters are ANDed: a seed wins only if it meets all of them. "X attacks and scores" is goal_by_team:<side of X>, never ends_in_goal (it would accept a rival goal). "X has a shot" is shot_by_team:<side>.
- goal_by:<full name> only for players in the catalog `players`; if the name is not there, leave it out and say so in the summary. Details such as a bicycle kick are not detected: say so in the summary.
- more_pressure:<side> and more_possession:<side> only rank the seeds, they do not filter, but they ARE entries of situation.wanted: add them there whenever the request asks for more pressure or more possession (never only in the summary). A matching style (high_press, possession) may accompany them.
- full_match has no wanted: requests such as a comeback, a goal at a given minute or a final score cannot be required. Return a full_match recipe and say in the summary that it cannot be demanded.
- A formation that is not in the catalog (e.g. 4-2-4): use the nearest catalog formation and say so in the summary.
- When editing the current recipe, keep everything the request does not ask to change: formations, styles, levels, seed, steps, template and ball_owner.
- If a current recipe is given and the request asks for a full match, set mode full_match, situation null, steps 3000, and keep the rest.
- A request for a goal by a player: put goal_by:<Name> in wanted using the name exactly as in `players` (e.g. goal_by:Mossvane). The player's team does not change ball_owner unless the request says who attacks. If the name is not in `players`, wanted has NO goal_by entry at all.
- Every filter the request asks for must appear in situation.wanted as a catalog token, e.g. "more possession for Wexmoor" -> more_possession:away; "more pressure from the home side" -> more_pressure:home. When editing, wanted = the existing entries plus the new ones (never replace them).
- summary: one or two English sentences for the UI, like "Wexmoor counter-attack (4-3-3, counter) against Brackenford; searching 200 seeds for a Wexmoor goal". Say what cannot be met.

Examples (when a current recipe is given, change only what the request names):
- "more possession for Wexmoor" on a recipe whose wanted is ["goal_by_team:away"] -> wanted ["goal_by_team:away", "more_possession:away"], everything else identical.
- "goal by Zzyzx" (not in players) -> no goal_by entry; the summary says the player does not exist in the catalog."""


def _instructions():
    c = catalog()
    for k in ("template_previews", "examples"):
        c.pop(k)
    return f"{RULES}\n\nCatalog:\n{json.dumps(c, ensure_ascii=False)}"


def _plain(v):
    """Drop the nulls (the seed keeps its null: it means "no fixed seed")."""
    return {k: _plain(x) if isinstance(x, dict) else x for k, x in v.items() if x is not None or k == "seed"}


def draft_recipe(text, recipe=None):
    """(request text, current recipe or None) -> {"recipe": dict, "summary": str}."""
    if not foundry.configured():
        raise NotImplementedError("scenario agent not implemented")
    message = f"Request: {text}\nCurrent recipe: {json.dumps(recipe) if recipe else 'none'}"
    out = foundry.run(_instructions(), message, response_format=ScenarioOutput, timeout_s=TIMEOUT_S, max_output_tokens=800)
    new = _plain(out.recipe.model_dump())
    sit, old = new.get("situation"), (recipe or {}).get("situation") or {}
    if sit and not sit.get("template"):  # positions/ball are not in the output schema: carry them over
        sit.update({k: old[k] for k in ("positions", "ball") if old.get(k) is not None})
    return {"recipe": new, "summary": out.summary}
