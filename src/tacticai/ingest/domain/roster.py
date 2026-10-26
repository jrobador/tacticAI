"""Roster published as roster.json (contract): stable player_id, team, name, shirt number, starting role."""
from .contract import player_id

PREFERRED = {"RB": [2], "LB": [3], "CB": [5, 4, 6, 15], "DM": [6, 4, 16], "CM": [8, 10, 14, 16, 18],
             "LM": [11, 7, 17], "RM": [7, 11, 19], "AM": [10, 8, 20], "CF": [9, 10, 19, 21]}


def shirt_numbers(roles):
    """Shirt number per player, from the role order: GK 1, else the first free number in the role's list, else the lowest free >= 12."""
    used, out = set(), []
    for r in roles:
        n = 1 if r == "GK" else next((n for n in PREFERRED.get(r, []) if n not in used), None)
        n = n or next(n for n in range(12, 100) if n not in used)
        used.add(n)
        out.append(n)
    return out


def build_roster(left_full, left_short, left_players, right_full, right_short, right_players):
    """players = [(last name, role name)] in *_team array order -> (teams for meta.json, roster.json dict)."""
    out = []
    for side, players in (("home", left_players), ("away", right_players)):
        nums = shirt_numbers([r for _, r in players])
        out += [{"player_id": player_id(side, i), "team": side, "name": n, "number": nums[i], "role": r}
                for i, (n, r) in enumerate(players)]
    teams = {"home": {"name": left_full, "short": left_short}, "away": {"name": right_full, "short": right_short}}
    return teams, {"players": out}
