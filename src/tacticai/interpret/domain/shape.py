"""Pure team geometry per row, oriented by team: xa = s*x towards the rival goal, ya = s*y, h = xa + L/2 metres from the own goal. Outfield players on the pitch only."""
from statistics import mean

from .frame import third
from .relative import flag_runs

LANES = ("left", "half_left", "center", "half_right", "right")
THIRDS = ("def_third", "mid_third", "att_third")
LOW_BLOCK_MIN_S = 2.0


def outfield(row, team):
    """[(xa, ya)] of the team's on-pitch outfield players."""
    s = 1 if team == "home" else -1
    return [(s * p["x"], s * p["y"]) for p in row["players"] if p["player_id"].startswith(team) and p["role"] != "GK" and p["on_pitch"]]


def row_metrics(row, team, length):
    """{block_height, defensive_line, length, width} in metres, or None without outfield players. defensive_line = mean h of the 4 deepest."""
    pts = outfield(row, team)
    if not pts:
        return None
    h = sorted(xa + length / 2 for xa, _ in pts)
    return {"block_height": mean(h), "defensive_line": mean(h[:4]), "length": max(xa for xa, _ in pts) - min(xa for xa, _ in pts),
            "width": max(ya for _, ya in pts) - min(ya for _, ya in pts)}


def lane(ya, width):
    return LANES[sum(ya >= c * width for c in (-0.3, -0.1, 0.1, 0.3))]


def occupation(rows, durs, idxs, team, length, width):
    """{third: {lane: {player_s, mean_players}}} over the rows idxs (seconds each outfield player spends in the cell; mean_players = player_s / total seconds)."""
    secs, total = {}, sum(durs[i] for i in idxs)
    for i in idxs:
        for xa, ya in outfield(rows[i], team):
            k = (third(xa, length), lane(ya, width))
            secs[k] = secs.get(k, 0.0) + durs[i]
    return {t: {ln: {"player_s": secs.get((t, ln), 0.0), "mean_players": secs.get((t, ln), 0.0) / total} for ln in LANES} for t in THIRDS}


def low_block_episodes(rows, phs, bh, length, q25, min_s=LOW_BLOCK_MIN_S):
    """[(i0, i1)] stretches defending ('opp' phase) with the block in the own half (h < L/2) and below the reference q25, lasting >= min_s. bh = {row index: block_height}."""
    return flag_runs(rows, [phs[i] == "opp" and i in bh and bh[i] < length / 2 and bh[i] < q25 for i in range(len(rows))], min_s)
