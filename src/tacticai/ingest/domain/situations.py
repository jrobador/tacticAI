"""Situation templates: starting positions per team, each in its OWN frame (attacking +x, +y = bottom touchline)."""


def _p(*rows):
    return [[x, y, role] for role, x, y in rows]


_WING_R = {
    "attack": _p(("GK", -1.0, 0), ("CB", -0.15, -0.10), ("CB", -0.15, 0.10), ("LB", 0.0, -0.28), ("DM", 0.05, 0.0),
                 ("CM", 0.25, -0.05), ("AM", 0.40, 0.10), ("RB", 0.35, 0.36), ("RM", 0.45, 0.30),
                 ("LM", 0.55, -0.20), ("CF", 0.65, 0.02)),
    "defend": _p(("GK", -1.0, 0), ("LB", -0.68, -0.26), ("CB", -0.78, -0.08), ("CB", -0.78, 0.08),
                 ("RB", -0.70, 0.24), ("LM", -0.58, -0.22), ("CM", -0.55, -0.08), ("CM", -0.55, 0.08),
                 ("RM", -0.50, 0.25), ("CF", -0.25, -0.05), ("CF", -0.20, 0.08)),
    "ball": [0.47, 0.30],
}
_SWAP = {"LB": "RB", "RB": "LB", "LM": "RM", "RM": "LM"}


def _mirror(t):
    flip = lambda pl: [[x, -y if y else 0, _SWAP.get(r, r)] for x, y, r in pl]
    return {"attack": flip(t["attack"]), "defend": flip(t["defend"]), "ball": [t["ball"][0], -t["ball"][1]]}


TEMPLATES = {
    "counter": {
        "attack": _p(("GK", -1.0, 0), ("LB", -0.45, -0.25), ("CB", -0.55, -0.08), ("CB", -0.55, 0.08),
                     ("RB", -0.45, 0.25), ("DM", -0.35, 0.0), ("CM", -0.15, 0.02), ("CM", -0.20, -0.12),
                     ("LM", 0.05, -0.30), ("RM", 0.05, 0.30), ("CF", 0.12, 0.0)),
        "defend": _p(("GK", -1.0, 0), ("LB", -0.18, -0.25), ("CB", -0.22, -0.08), ("CB", -0.22, 0.08),
                     ("RB", -0.18, 0.25), ("LM", 0.25, -0.28), ("CM", 0.22, -0.08), ("CM", 0.22, 0.08),
                     ("RM", 0.25, 0.28), ("CF", 0.45, -0.05), ("CF", 0.45, 0.08)),
        "ball": [-0.13, 0.02],
    },
    "wing_attack_right": _WING_R,
    "wing_attack_left": _mirror(_WING_R),
    "build_up": {
        "attack": _p(("GK", -0.95, 0), ("CB", -0.80, 0.12), ("CB", -0.80, -0.12), ("LB", -0.60, -0.32),
                     ("RB", -0.60, 0.32), ("DM", -0.60, 0.0), ("CM", -0.40, -0.12), ("CM", -0.40, 0.12),
                     ("LM", -0.15, -0.30), ("RM", -0.15, 0.30), ("CF", 0.05, 0.0)),
        "defend": _p(("GK", -1.0, 0), ("CB", -0.30, -0.08), ("CB", -0.30, 0.08), ("LB", -0.15, -0.25),
                     ("RB", -0.15, 0.25), ("CM", 0.20, -0.10), ("CM", 0.20, 0.10), ("LM", 0.35, -0.25),
                     ("RM", 0.35, 0.25), ("CF", 0.62, -0.06), ("CF", 0.62, 0.10)),
        "ball": [-0.78, 0.12],
    },
}


def resolve(name, owner):
    """(positions {"home","away"}, absolute ball [x, y]) for a template; `owner` ("home"/"away") attacks."""
    t = TEMPLATES[name]
    attack, defend, (bx, by) = [list(p) for p in t["attack"]], [list(p) for p in t["defend"]], t["ball"]
    if owner == "home":
        return {"home": attack, "away": defend}, [bx, by]
    return {"home": defend, "away": attack}, [-bx, -by]
