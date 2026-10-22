"""Roster published as roster.json: who is at each index of the *_team arrays."""


def build_roster(left_full, left_short, left_players, right_full, right_short, right_players):
    """players = [(last name, role name)] in *_team array order."""
    def side(full, short, players):
        return {"team": full, "short": short,
                "players": [{"index": i, "name": n, "role": r} for i, (n, r) in enumerate(players)]}
    return {"left": side(left_full, left_short, left_players), "right": side(right_full, right_short, right_players)}
