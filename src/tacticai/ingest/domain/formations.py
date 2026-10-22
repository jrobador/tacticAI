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


def build_team(name, kickoff):
    pl = [list(p) for p in FORMATIONS[name]]
    if kickoff:
        for p, y in zip(sorted(pl, key=lambda p: -p[0])[:2], (-0.02, 0.02)):
            p[0], p[1] = 0.0, y
    else:
        for p in pl:
            p[0] = min(p[0], -0.10)
    return pl


def choose(seed):
    """(left formation, right formation, kickoff side) for a seed."""
    rng = random.Random(seed)
    return rng.choice(list(FORMATIONS)), rng.choice(list(FORMATIONS)), "left" if seed % 2 == 0 else "right"
