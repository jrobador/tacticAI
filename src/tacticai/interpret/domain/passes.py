"""Pure pass statistics from contract events. Progressive = gain toward the opponent goal along x (+x home, -x away) of at least PROGRESSIVE_M, completed."""
import math

from .frame import opponent, release_index, third, x_att
from .lines import lines_crossed
from .physical import open_play_seconds
from .pressure import pressure_on
from .shots import dist_to_segment

PROGRESSIVE_M = 10.0


def _agg(ps, mins):
    n, done = len(ps), [p for p in ps if p["outcome"] == "complete"]
    return {"passes": n, "completed": len(done), "completion_pct": 100 * len(done) / n if n else None,
            "mean_length_m": sum(p["length_m"] for p in ps) / n if n else None,
            "passes_per_min": n / mins if mins else None,
            "progressive_passes": sum(p["progressive_m"] >= PROGRESSIVE_M for p in done)}


def pass_stats(events, rows):
    """-> {"passes": [pass fields + length_m, progressive_m], "players": {player_id: agg}, "teams": {team: agg}}."""
    ps = [{"frame_index": e["frame_index"], "team": e["team"], "player_id": e["player_id"], "to_player_id": e["to_player_id"],
           "outcome": e["outcome"], "length_m": math.dist((e["x"], e["y"]), (e["end_x"], e["end_y"])),
           "progressive_m": x_att(e["end_x"], e["team"]) - x_att(e["x"], e["team"])} for e in events if e["type"] == "pass"]
    mins = open_play_seconds(rows) / 60
    by = lambda k: {v: _agg([p for p in ps if p[k] == v], mins) for v in sorted({p[k] for p in ps})}
    return {"passes": ps, "players": by("player_id"), "teams": by("team")}


NEAR_LINE_M = 2.0


def pass_features(rows, owners, events, idx, meta):
    """One flat feature dict per pass event (any outcome), measured at the release row (last row the passer owned); label `complete`."""
    out, length = [], meta["pitch"]["length_m"]
    for e in events:
        if e["type"] != "pass":
            continue
        r, t = rows[(k := release_index(rows, owners, e, idx))], e["team"]
        a, b = (e["x"], e["y"]), (e["end_x"], e["end_y"])
        foes = [(p["x"], p["y"]) for p in r["players"] if p["on_pitch"] and p["player_id"].startswith(opponent(t))]
        me = next((p for p in r["players"] if p["player_id"] == e["player_id"]), None)
        out.append(dict(match_id=meta["match_id"], frame_index=e["frame_index"], release_frame_index=r["frame_index"], t_s=e["t_s"], team=t,
                        passer_id=e["player_id"], passer_role=me and me["role"], start_x_att=x_att(e["x"], t), end_x_att=x_att(e["end_x"], t),
                        length_m=math.dist(a, b), progressive_m=x_att(e["end_x"], t) - x_att(e["x"], t), start_third=third(x_att(e["x"], t), length),
                        passer_pressure=pressure_on(r, e["player_id"]), opponents_near_line=sum(dist_to_segment(f, a, b) <= NEAR_LINE_M for f in foes),
                        nearest_opponent_to_receiver_m=min((math.dist(f, b) for f in foes), default=None), lines_broken=lines_crossed(e, r),
                        game_state=r["game_state"], score_diff=r["score"][t] - r["score"][opponent(t)], complete=e["outcome"] == "complete"))
    return out
