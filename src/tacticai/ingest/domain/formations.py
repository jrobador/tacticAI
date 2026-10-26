"""Formations and per-seed choices. Roles are plain names; the engine adapter maps them to engine roles."""
import random

FORMATIONS = {
    "4-4-2": [(-1.0, 0, "GK"), (-0.42, -0.20, "LB"), (-0.50, -0.07, "CB"),
              (-0.50, 0.07, "CB"), (-0.42, 0.20, "RB"), (-0.18, -0.22, "LM"),
              (-0.25, -0.06, "CM"), (-0.25, 0.06, "CM"), (-0.18, 0.22, "RM"),
              (-0.02, -0.03, "CF"), (-0.02, 0.03, "CF")],
    "4-3-3": [(-1.0, 0, "GK"), (-0.42, -0.20, "LB"), (-0.50, -0.07, "CB"),
              (-0.50, 0.07, "CB"), (-0.42, 0.20, "RB"), (-0.27, -0.10, "CM"),
              (-0.32, 0, "DM"), (-0.27, 0.10, "CM"), (-0.05, -0.22, "LM"),
              (-0.02, 0, "CF"), (-0.05, 0.22, "RM")],
}


def _apply_kickoff(pl, kickoff):
    if kickoff:
        for p, y in zip(sorted(pl, key=lambda p: -p[0])[:2], (-0.02, 0.02)):
            p[0], p[1] = 0.0, y
    else:
        for p in pl:
            p[0] = min(p[0], -0.10)
    return pl


def build_team(name, kickoff):
    return _apply_kickoff([list(p) for p in FORMATIONS[name]], kickoff)


def choose(seed):
    """(left formation, right formation, kickoff side) for a seed."""
    rng = random.Random(seed)
    return rng.choice(list(FORMATIONS)), rng.choice(list(FORMATIONS)), "left" if seed % 2 == 0 else "right"


# CATALOG: (role, shape_x, shape_y) in formation space: x -1 own goal .. +1 opponent, +y = left of the team.
# GK first, then defenders (+y first), midfielders, forwards.
_BACK4 = [("LB", -0.75, 0.8), ("CB", -0.95, 0.25), ("CB", -0.95, -0.25), ("RB", -0.75, -0.8)]
_BACK3 = [("CB", -0.95, 0.4), ("CB", -0.95, 0.0), ("CB", -0.95, -0.4)]
_BACK5 = [("LB", -0.55, 0.9), ("CB", -0.95, 0.4), ("CB", -0.95, 0.0), ("CB", -0.95, -0.4), ("RB", -0.55, -0.9)]
_TWO_CF = [("CF", 1.0, 0.25), ("CF", 1.0, -0.25)]
_ONE_CF = [("CF", 1.0, 0.0)]
_FOUR_MID = [("LM", 0.05, 0.8), ("CM", -0.15, 0.35), ("CM", -0.15, -0.35), ("RM", 0.05, -0.8)]
_THREE_CM = [("CM", -0.15, 0.45), ("CM", -0.15, 0.0), ("CM", -0.15, -0.45)]
_GK = [("GK", -1.0, 0.0)]

CATALOG = {
    "4-4-2": _GK + _BACK4 + _FOUR_MID + _TWO_CF,
    "4-3-3": _GK + _BACK4 + [("CM", -0.15, 0.45), ("DM", -0.45, 0.0), ("CM", -0.15, -0.45),
                             ("LM", 0.6, 0.75), ("CF", 1.0, 0.0), ("RM", 0.6, -0.75)],
    "4-2-3-1": _GK + _BACK4 + [("DM", -0.45, 0.35), ("DM", -0.45, -0.35),
                               ("LM", 0.2, 0.8), ("AM", 0.35, 0.0), ("RM", 0.2, -0.8)] + _ONE_CF,
    "4-1-4-1": _GK + _BACK4 + [("DM", -0.45, 0.0)] + _FOUR_MID + _ONE_CF,
    "3-5-2": _GK + _BACK3 + [("LB", -0.55, 0.9), ("CM", -0.15, 0.4), ("DM", -0.45, 0.0),
                             ("CM", -0.15, -0.4), ("RB", -0.55, -0.9)] + _TWO_CF,
    "3-4-3": _GK + _BACK3 + [("LB", -0.55, 0.9), ("CM", -0.15, 0.35), ("CM", -0.15, -0.35), ("RB", -0.55, -0.9),
                             ("LM", 0.6, 0.75), ("CF", 1.0, 0.0), ("RM", 0.6, -0.75)],
    "5-3-2": _GK + _BACK5 + _THREE_CM + _TWO_CF,
    "5-4-1": _GK + _BACK5 + _FOUR_MID + _ONE_CF,
}


def kickoff_positions(entries, kickoff):
    """Observation-space start positions [x, y, role] (own half) from catalog entries."""
    pl = [[-1.0 if role == "GK" else -1 + (x + 1) / 2 * 0.95, -y * 0.38, role] for role, x, y in entries]
    return _apply_kickoff(pl, kickoff)


def shape_vector(name):
    return [v for _, x, y in CATALOG[name] for v in (x, y)]


def roles(name):
    return [r for r, _, _ in CATALOG[name]]
