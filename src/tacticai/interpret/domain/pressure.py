"""Pure pressure metrics: opponents closing down a player. Pressure on a player = sum over on-pitch opponents (GK included) within RADIUS_M of 1 - d/RADIUS_M, capped at 1."""
import math

from ...ingest.domain.contract import team_of
from ...ingest.domain.events import DEFAULTS, infer_owner, stable_owners
from .frame import opponent
from .physical import is_open

RADIUS_M = 5.0


def pressure_on(row, player_id):
    """0..1; 0.0 when the player is not on the pitch."""
    me = next((p for p in row["players"] if p["player_id"] == player_id and p["on_pitch"]), None)
    if me is None:
        return 0.0
    foe = opponent(team_of(player_id))
    return min(1.0, sum(1 - d / RADIUS_M for p in row["players"]
                        if p["on_pitch"] and team_of(p["player_id"]) == foe and (d := math.dist((p["x"], p["y"]), (me["x"], me["y"]))) < RADIUS_M))


def owners_for(rows, th=DEFAULTS):
    """Stable owners aligned with rows: (team, player_id) or None. Same construction as ingest/domain/events.extract."""
    return stable_owners([infer_owner(r, th["owner_radius_m"], th["owner_max_z_m"]) for r in rows], th["owner_min_frames"])


def team_pressure(rows, owners, team, t0=None, t1=None):
    """Mean pressure `team` applies on the opponent's stable owner over open-play rows (t0 <= t_s < t1 when given); None without such rows."""
    foe = opponent(team)
    v = [pressure_on(r, o[1]) for r, o in zip(rows, owners)
         if o and o[0] == foe and is_open(r) and (t0 is None or r["t_s"] >= t0) and (t1 is None or r["t_s"] < t1)]
    return sum(v) / len(v) if v else None
