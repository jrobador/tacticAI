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


PRESS_MIN_S = 0.5


def pressing_events(rows, owners, radius_m=RADIUS_M, min_s=PRESS_MIN_S):
    """{player_id: n}: continuous stretches (consecutive open-play frames, opponent stable owner, player within radius_m of that owner) lasting >= min_s
    (last t_s - first t_s + frame step)."""
    out, cur, step = {}, {}, (rows[1]["t_s"] - rows[0]["t_s"]) if len(rows) > 1 else 0.0

    def end(pid):
        t0, t1 = cur.pop(pid)
        out[pid] = out.get(pid, 0) + (t1 - t0 + step >= min_s - 1e-9)

    for i, r in enumerate(rows):
        o, near = owners[i], set()
        me = o and is_open(r) and (i == 0 or r["frame_index"] == rows[i - 1]["frame_index"] + 1) and next((p for p in r["players"] if p["player_id"] == o[1]), None)
        if me:
            near = {p["player_id"] for p in r["players"] if p["on_pitch"] and team_of(p["player_id"]) == opponent(o[0])
                    and math.dist((p["x"], p["y"]), (me["x"], me["y"])) < radius_m}
        for pid in [k for k in cur if k not in near]:
            end(pid)
        for pid in near:
            cur.setdefault(pid, [r["t_s"], r["t_s"]])[1] = r["t_s"]
    for pid in list(cur):
        end(pid)
    return out
