"""Shared attacking-direction helpers: everything that measures advance uses x_att, the x oriented towards the opponent goal."""


def x_att(x, team):
    """x for home, -x for away."""
    return x if team == "home" else -x


def third(xa, length_m):
    """Pitch third of an x_att value: def_third, mid_third or att_third."""
    return "def_third" if xa < -length_m / 6 else "att_third" if xa >= length_m / 6 else "mid_third"


def by_frame(rows):
    return {r["frame_index"]: r for r in rows}


def release_index(rows, owners, event, idx):
    """Row index where the passer last owned the ball before the reception row of `event`: walks back over consecutive open-play rows;
    the event row itself when the passer does not own any of them."""
    me, i = (event["team"], event["player_id"]), idx[event["frame_index"]]
    for k in range(i, -1, -1):
        if owners[k] == me:
            return k
        if k and (rows[k]["frame_index"] - rows[k - 1]["frame_index"] > 1 or rows[k - 1]["game_state"] != "open_play"):
            break
    return i


def opponent(team):
    return "away" if team == "home" else "home"
