"""Recipe validation (Pydantic shape, then the domain) and the catalog: shared by the API and the scenario agent."""
import json
import os
import re

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from ..domain import recipe as recipe_mod
from ..domain import situations
from ..domain.formations import CATALOG
from ..domain.pitch import ENG_X, ENG_Y
from ..domain.styles import STYLES


class _Shape(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")


class TeamShape(_Shape):
    formation: str = "4-4-2"
    style: str = "balanced"
    level: float = 1.0


def _check_positions(positions):
    if positions is None:
        return positions
    for side, players in positions.items():
        ok = isinstance(players, list) and all(
            isinstance(p, list) and len(p) == 3 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p[:2])
            and isinstance(p[2], str) for p in players)
        if not ok:
            raise ValueError(f"positions.{side} must be a list of [x, y, role] with numbers and a string role")
    return positions


class SituationShape(_Shape):
    start: str = ""
    positions: dict | None = None
    ball: list | None = None
    ball_owner: str | None = None
    ends_when: str = "steps"
    wanted: list[str] = []
    template: str | None = None

    _positions = field_validator("positions")(_check_positions)


class RecipeShape(_Shape):
    mode: str | None = None
    home: TeamShape = TeamShape()
    away: TeamShape = TeamShape()
    situation: SituationShape | None = None
    seeds: int = 1
    steps: int | None = None
    seed: int | None = 0


def _issue(path, message):
    return {"path": path, "message": message}


def _domain_issue(message):
    """RecipeError messages look like "home: unknown formation 'x'": split them into path and message."""
    m = re.match(r"^([a-z_.]+): (.*)$", message)
    if not m:
        return _issue("", message)
    path = m.group(1)
    for field in ("formation", "style", "level"):
        if path in ("home", "away") and field in m.group(2):
            path += "." + field
    return _issue(path, m.group(2))


def check_recipe(d):
    """Both validation steps -> list of {"path", "message"}; empty when the recipe is valid."""
    if not isinstance(d, dict):
        return [_issue("", "recipe must be an object")]
    try:
        RecipeShape.model_validate(d)
    except ValidationError as err:
        return [_issue(".".join(map(str, e["loc"])), e["msg"]) for e in err.errors()]
    try:
        recipe_mod.from_dict(d)
    except recipe_mod.RecipeError as err:
        return [_domain_issue(m) for m in err.messages]
    return _product_limits(d)


def _product_limits(d):
    """Product limits (catalog "limits"); the domain and the CLI stay more permissive."""
    errs = []
    for side in ("home", "away"):
        level = (d.get(side) or {}).get("level", 1.0)
        if not 0.7 <= level <= 1.0:
            errs.append(_issue(f"{side}.level", "level must be in 0.7..1.0"))
    if d.get("mode") == "situation" and d.get("steps", 300) != 300:
        errs.append(_issue("steps", "steps must be 300 for situations"))
    return errs



WANTED = [
    {"name": "ends_in_shot", "takes": None, "description": "Either team has a shot or goal in the clip"},
    {"name": "ends_in_goal", "takes": None, "description": "Either team scores"},
    {"name": "goal_by_team", "takes": "side", "description": "The chosen team scores"},
    {"name": "shot_by_team", "takes": "side", "description": "The chosen team has a shot or goal"},
    {"name": "goal_by", "takes": "player", "description": "A specific player scores (full name)"},
    {"name": "more_pressure", "takes": "side",
     "description": "Orders the seeds by recoveries in the rival half per minute; does not filter"},
    {"name": "more_possession", "takes": "side",
     "description": "Orders the seeds by share of possession; does not filter"},
]


def template_previews():
    """Per template and ball_owner: both teams and the ball in contract metres, absolute (away mirrored on both axes)."""
    def pts(players, sign):
        return [{"role": r, "x": round(sign * x * ENG_X, 2), "y": round(sign * y * ENG_Y, 2)} for x, y, r in players]
    out = {}
    for name in situations.TEMPLATES:
        out[name] = {}
        for owner in recipe_mod.SIDES:
            pos, (bx, by) = situations.resolve(name, owner)
            out[name][owner] = {"home": pts(pos["home"], 1), "away": pts(pos["away"], -1),
                                "ball": {"x": round(bx * ENG_X, 2), "y": round(by * ENG_Y, 2)}}
    return out


def _players():
    """Players of the first published match, else of the first library entry that has a roster."""
    from ...api import files  # lazy: api.files pulls orchestration, which imports ingest
    roots = files.roots()
    for kind in ("matches", "library"):
        for d in sorted(os.listdir(roots[kind])) if os.path.isdir(roots[kind]) else []:
            path = os.path.join(roots[kind], d, "roster.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    return [{"name": p["name"], "team": p["team"], "number": p["number"]} for p in json.load(f)["players"]]
    return []

def catalog():
    return {"formations": list(CATALOG), "styles": list(STYLES), "templates": list(situations.TEMPLATES),
            "modes": ["full_match", "situation"], "ends_when": list(recipe_mod.ENDS), "wanted": WANTED,
            "limits": {"seeds": {"min": 1, "max": 200}, "level": {"min": 0.7, "max": 1.0}, "steps_situation": 300},
            "template_previews": template_previews(),
            "examples": [recipe_mod.to_dict(r) for r in recipe_mod.example_recipes()], "players": _players()}
