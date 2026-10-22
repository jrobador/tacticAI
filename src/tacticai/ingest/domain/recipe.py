"""The match recipe: what to simulate. Home = left team (attacks +x), away = right team."""
from dataclasses import dataclass, field

from .formations import CATALOG
from .situations import TEMPLATES
from .styles import STYLES

ROLES = {"GK", "CB", "LB", "RB", "DM", "CM", "LM", "RM", "AM", "CF"}
ENDS = ("goal", "possession_change", "out_of_play", "steps")
SIMPLE_PREDICATES = {"ends_in_shot", "ends_in_goal"}
SIDE_PREDICATES = {"goal_by_team", "more_pressure", "more_possession"}
SIDES = ("home", "away")
MAX_Y = 0.42


class RecipeError(ValueError):
    def __init__(self, messages):
        super().__init__("; ".join(messages))
        self.messages = list(messages)


@dataclass
class TeamPlan:
    formation: str = "4-4-2"
    style: str = "balanced"
    level: float = 1.0


@dataclass
class Situation:
    start: str = ""
    positions: dict | None = None
    ball: list | None = None
    ball_owner: str | None = None
    ends_when: str = "steps"
    wanted: list = field(default_factory=list)
    template: str | None = None


@dataclass
class Recipe:
    mode: str
    home: TeamPlan
    away: TeamPlan
    situation: Situation | None = None
    seeds: int = 1
    steps: int = 3000
    seed: int | None = 0


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _team_from(d):
    d = d or {}
    return TeamPlan(d.get("formation", "4-4-2"), d.get("style", "balanced"), d.get("level", 1.0))


def from_dict(d):
    mode = d.get("mode")
    s = d.get("situation")
    sit = None if s is None else Situation(
        s.get("start", ""), s.get("positions"), s.get("ball"), s.get("ball_owner"),
        s.get("ends_when", "steps"), list(s.get("wanted", [])), s.get("template"))
    r = Recipe(mode, _team_from(d.get("home")), _team_from(d.get("away")), sit,
               d.get("seeds", 1), d.get("steps", 300 if mode == "situation" else 3000), d.get("seed", 0))
    errs = validate(r)
    if errs:
        raise RecipeError(errs)
    return r


def to_dict(r):
    def team(t):
        return {"formation": t.formation, "style": t.style, "level": t.level}
    s = r.situation
    return {"mode": r.mode, "home": team(r.home), "away": team(r.away),
            "situation": None if s is None else {
                "start": s.start, "positions": s.positions, "ball": s.ball, "ball_owner": s.ball_owner,
                "ends_when": s.ends_when, "wanted": list(s.wanted), "template": s.template},
            "seeds": r.seeds, "steps": r.steps, "seed": r.seed}


def _check_team(side, t, errs):
    if t.formation not in CATALOG:
        errs.append(f"{side}: unknown formation {t.formation!r}")
    if t.style not in STYLES:
        errs.append(f"{side}: unknown style {t.style!r}")
    if not _num(t.level) or not 0 <= t.level <= 1:
        errs.append(f"{side}: level must be a number in 0..1")


def _check_positions(side, pl, errs):
    if not isinstance(pl, list) or len(pl) != 11:
        errs.append(f"positions.{side}: need exactly 11 players")
        return
    roles = [p[2] if isinstance(p, (list, tuple)) and len(p) == 3 else None for p in pl]
    if roles.count("GK") != 1:
        errs.append(f"positions.{side}: need exactly one GK")
    for p, role in zip(pl, roles):
        if role not in ROLES:
            errs.append(f"positions.{side}: bad role {role!r}")
        elif not (_num(p[0]) and _num(p[1]) and -1 <= p[0] <= 1 and -MAX_Y <= p[1] <= MAX_Y):
            errs.append(f"positions.{side}: {role} outside pitch (x in -1..1, y in -{MAX_Y}..{MAX_Y})")


def _check_predicate(p, errs):
    name, _, arg = str(p).partition(":")
    if name in SIMPLE_PREDICATES and not arg:
        return
    if name == "goal_by" and arg:
        return
    if name in SIDE_PREDICATES and arg in SIDES:
        return
    errs.append(f"bad predicate {p!r}")


def validate(r):
    errs = []
    if r.mode not in ("full_match", "situation"):
        errs.append(f"mode must be full_match or situation, got {r.mode!r}")
    elif (r.mode == "situation") != (r.situation is not None):
        errs.append("situation is required iff mode is situation")
    _check_team("home", r.home, errs)
    _check_team("away", r.away, errs)
    if not isinstance(r.seeds, int) or not 1 <= r.seeds <= 200:
        errs.append("seeds must be an int in 1..200")
    if not isinstance(r.steps, int) or not 1 <= r.steps <= 3000:
        errs.append("steps must be an int in 1..3000")
    if r.seed is not None and not isinstance(r.seed, int):
        errs.append("seed must be an int or null")
    s = r.situation
    if s is not None:
        if s.positions is not None:
            if not isinstance(s.positions, dict) or set(s.positions) != set(SIDES):
                errs.append("positions must have exactly the keys home and away")
            else:
                for side in SIDES:
                    _check_positions(side, s.positions[side], errs)
        if s.ball is not None and not (
                isinstance(s.ball, (list, tuple)) and len(s.ball) == 2 and all(_num(v) for v in s.ball)
                and -1 <= s.ball[0] <= 1 and -MAX_Y <= s.ball[1] <= MAX_Y):
            errs.append(f"ball outside pitch (x in -1..1, y in -{MAX_Y}..{MAX_Y})")
        if s.ball_owner not in (None, *SIDES):
            errs.append("ball_owner must be home, away or null")
        if s.template is not None:
            if s.template not in TEMPLATES:
                errs.append(f"unknown template {s.template!r}")
            if s.positions is not None or s.ball is not None:
                errs.append("template excludes positions and ball")
            if s.ball_owner not in SIDES:
                errs.append("template needs ball_owner")
        if s.ends_when not in ENDS:
            errs.append(f"ends_when must be one of {ENDS}")
        for p in s.wanted:
            _check_predicate(p, errs)
    return errs


def example_recipes():
    full = from_dict({"mode": "full_match", "home": {"formation": "4-3-3", "style": "possession"},
                      "away": {"formation": "5-4-1", "style": "counter", "level": 0.8}, "seeds": 20})
    sit = from_dict({"mode": "situation", "home": {"formation": "4-2-3-1", "style": "counter"},
                     "away": {"formation": "4-4-2", "style": "balanced"},
                     "situation": {"start": "contraataque por la izquierda que termina en tiro",
                                   "ball": [-0.3, 0.2], "ball_owner": "home",
                                   "ends_when": "possession_change", "wanted": ["ends_in_shot"]},
                     "seeds": 50})
    counter = from_dict({"mode": "situation", "home": {"formation": "4-3-3", "style": "counter"},
                         "away": {"formation": "4-4-2", "style": "balanced"},
                         "situation": {"start": "contraataque del local", "template": "counter", "ball_owner": "home",
                                       "ends_when": "possession_change", "wanted": ["ends_in_shot"]},
                         "seeds": 50})
    return [full, sit, counter]
