"""Pure pressure metrics: opponents closing down a player. Pressure on a player = sum over on-pitch opponents (GK included) within RADIUS_M of 1 - d/RADIUS_M, capped at 1."""
import math

from ...ingest.domain.contract import team_of
from ...ingest.domain.events import DEFAULTS, infer_owner, stable_owners
from .frame import opponent, third, x_att
from .physical import is_open
from .relative import flag_runs

RADIUS_M = 5.0


def pressure_on(row, player_id):
    """0..1; 0.0 when the player is not on the pitch."""
    me = next((p for p in row["players"] if p["player_id"] == player_id and p["on_pitch"]), None)
    if me is None:
        return 0.0
    foe = opponent(team_of(player_id))
    return min(1.0, sum(1 - d / RADIUS_M for p in row["players"]
                        if p["on_pitch"] and team_of(p["player_id"]) == foe and (d := math.dist((p["x"], p["y"]), (me["x"], me["y"]))) < RADIUS_M))


def owners_for(rows, th=DEFAULTS, raw=None):
    """Stable owners aligned with rows: (team, player_id) or None. Same construction as ingest/domain/events.extract; raw: precomputed infer_owner per row."""
    return stable_owners(raw or [infer_owner(r, th["owner_radius_m"], th["owner_max_z_m"]) for r in rows], th["owner_min_frames"])


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


def pressure_series(rows, owners, team):
    """{row index: pressure} that `team` applies on the opponent's stable owner (open-play rows)."""
    foe = opponent(team)
    return {i: pressure_on(r, o[1]) for i, (r, o) in enumerate(zip(rows, owners)) if o and o[0] == foe and is_open(r)}


def pressing_episodes(rows, owners, radius_m=RADIUS_M, min_s=PRESS_MIN_S):
    """[{player_id, team, i0, i1, t0, t1}]: same stretches as pressing_events (one defender within radius_m of the opponent stable owner, consecutive open-play frames)
    lasting >= min_s, with their row indices; team = the pressing team."""
    out, cur, step = [], {}, (rows[1]["t_s"] - rows[0]["t_s"]) if len(rows) > 1 else 0.0

    def end(pid):
        i0, i1 = cur.pop(pid)
        if rows[i1]["t_s"] - rows[i0]["t_s"] + step >= min_s - 1e-9:
            out.append({"player_id": pid, "team": team_of(pid), "i0": i0, "i1": i1, "t0": rows[i0]["t_s"], "t1": rows[i1]["t_s"]})

    for i, r in enumerate(rows):
        o, near = owners[i], set()
        me = o and is_open(r) and (i == 0 or r["frame_index"] == rows[i - 1]["frame_index"] + 1) and next((p for p in r["players"] if p["player_id"] == o[1]), None)
        if me:
            near = {p["player_id"] for p in r["players"] if p["on_pitch"] and team_of(p["player_id"]) == opponent(o[0])
                    and math.dist((p["x"], p["y"]), (me["x"], me["y"])) < radius_m}
        for pid in [k for k in cur if k not in near]:
            end(pid)
        for pid in near:
            cur.setdefault(pid, [i, i])[1] = i
    for pid in list(cur):
        end(pid)
    return sorted(out, key=lambda e: (e["i0"], e["player_id"]))


def high_press_episodes(rows, pres, team, length, q75, min_s=PRESS_MIN_S):
    """[(i0, i1)] stretches where the opponent owner carries the ball in the attacking third of `team` (xa >= L/6) under pressure >= q75 (pres = pressure_series), lasting >= min_s."""
    return flag_runs(rows, [i in pres and pres[i] >= q75 and x_att(r["ball"]["x"], team) >= length / 6 for i, r in enumerate(rows)], min_s)


def recoveries(indexed, team, length):
    """[{event_index, t_s, kind, xa, third}]: tackles by `team` (located at the tackle) and interceptions by `team` (located at the pass end). indexed = [(event index, event)]."""
    out = []
    for j, e in indexed:
        if e["type"] == "tackle" and e["team"] == team:
            kind, x = "tackle", e["x"]
        elif e["type"] == "pass" and e["outcome"] == "intercepted" and e["intercepted_by"] and team_of(e["intercepted_by"]) == team:
            kind, x = "interception", e["end_x"]
        else:
            continue
        xa = x_att(x, team)
        out.append({"event_index": j, "t_s": e["t_s"], "kind": kind, "xa": xa, "third": third(xa, length)})
    return out


def ppda_proxy(indexed, recs, team, length):
    """(rival recorded passes starting at xa >= -L/10 in the team's frame, own recoveries there). Not the official PPDA: fouls and duels are not in the data."""
    foe = opponent(team)
    passes = sum(e["type"] == "pass" and e["team"] == foe and x_att(e["x"], team) >= -length / 10 for _, e in indexed)
    return passes, sum(r["xa"] >= -length / 10 for r in recs)


def press_outcomes(episodes, recs, after_s=3.0):
    """Number of pressing episodes followed by a recovery of the pressing team from the episode start up to after_s after its end (temporal association only)."""
    return sum(any(e["t0"] <= r["t_s"] <= e["t1"] + after_s for r in recs) for e in episodes)
