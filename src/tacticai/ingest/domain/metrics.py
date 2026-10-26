"""Pure team-shape and style metrics over contract tracking frames (metres). Forward is positive for both sides.
`half` = meta.pitch.length_m / 2: forward is measured from the team's own goal line."""
import math
from statistics import mean

from .clock import FRAME_S
from .contract import team_of

OTHER = {"home": "away", "away": "home"}


def outfield(row, side, half):
    """[(forward m from own goal line, lateral m)] for the team's on-pitch outfield players (GK excluded)."""
    sign = 1 if side == "home" else -1
    return [(sign * p["x"] + half, p["y"]) for p in row["players"]
            if team_of(p["player_id"]) == side and p["role"] != "GK" and p["on_pitch"]]


def phase_rows(rows, side, possession):
    """Rows where `side` owns the ball (possession=True) or the opponent does (False); loose-ball rows are skipped."""
    return [r for r in rows if r["possession"]["team"] == (side if possession else OTHER[side])]


def _mean(vals):
    return mean(vals) if vals else None


def defensive_line_height(rows, side, half):
    """Mean forward position of the 4 deepest outfield players while defending."""
    return _mean([mean(sorted(f for f, _ in outfield(r, side, half))[:4]) for r in phase_rows(rows, side, False)])


def block_height(rows, side, half, possession=False):
    return _mean([mean(f for f, _ in outfield(r, side, half)) for r in phase_rows(rows, side, possession)])


def _spread(rows, side, half, possession, axis):
    """Mean (max - min) of one axis (0 forward, 1 lateral) over outfield players."""
    vals = [[p[axis] for p in outfield(r, side, half)] for r in phase_rows(rows, side, possession)]
    return _mean([max(v) - min(v) for v in vals])


def team_length(rows, side, half, possession=False):
    return _spread(rows, side, half, possession, 0)


def team_width(rows, side, half, possession=False):
    return _spread(rows, side, half, possession, 1)


def possession_pct(rows, side):
    """Share of rows owned by `side`, over all rows."""
    return 100 * sum(r["possession"]["team"] == side for r in rows) / len(rows) if rows else None


def recoveries_opp_half_per_min(rows, events, side):
    """Tackles won + interceptions by `side` where the ball ends in the opponent half, per in-play minute."""
    sign = 1 if side == "home" else -1
    n = 0
    for e in events:
        if e["type"] == "tackle" and e["team"] == side:
            x = e["x"]
        elif e["type"] == "pass" and e["outcome"] == "intercepted" and e["team"] != side:
            x = e["end_x"]
        else:
            continue
        n += sign * x > 0
    return n / (len(rows) * FRAME_S / 60) if rows else None


def mean_pass_length_m(events, side):
    ds = [math.dist((e["x"], e["y"]), (e["end_x"], e["end_y"])) for e in events
          if e["type"] == "pass" and e["outcome"] == "complete" and e["team"] == side]
    return _mean(ds)


def all_metrics(rows, events, side, half):
    return {
        "defensive_line_height": defensive_line_height(rows, side, half),
        "block_height_def": block_height(rows, side, half),
        "block_height_pos": block_height(rows, side, half, True),
        "team_width_def": team_width(rows, side, half),
        "team_length_def": team_length(rows, side, half),
        "possession_pct": possession_pct(rows, side),
        "recoveries_opp_half_per_min": recoveries_opp_half_per_min(rows, events, side),
        "mean_pass_length_m": mean_pass_length_m(events, side),
    }
