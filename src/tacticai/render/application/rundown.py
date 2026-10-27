"""render/broadcast/rundown.json: the broadcast graphics of a match (render/domain/rundown.py) from its analysis and tracking."""
import bisect
import json
import math
import os

from ...core.files import read_json, read_jsonl, write_atomic
from ...ingest.domain.contract import team_of
from ...interpret.domain import physical
from ..domain import rundown


def _travelled(rows):
    """travelled(player_id, t) -> metres the player covered from kick-off to video time t."""
    acc = {}
    for a, b in zip(rows, rows[1:]):
        pa = {p["player_id"]: p for p in a["players"]}
        for p in b["players"]:
            q = pa.get(p["player_id"])
            if q:
                ts, ds = acc.setdefault(p["player_id"], ([], []))
                ts.append(b["t_s"])
                ds.append((ds[-1] if ds else 0.0) + math.dist((q["x"], q["y"]), (p["x"], p["y"])))

    def at(pid, t):
        ts, ds = acc.get(pid, ([], []))
        i = bisect.bisect_right(ts, t)
        return ds[i - 1] if i else 0.0
    return at


def _net_at(rows, half):
    """net_at(shot_t) -> video second of the first tracking row after the shot with the ball at the goal line (|x| >= half); shot + 1 s when it takes over 3 s."""
    def at(t):
        r = next((r for r in rows if r["t_s"] > t and abs(r["ball"]["x"]) >= half), None)
        return round(r["t_s"] if r and r["t_s"] - t <= 3 else t + 1.0, 1)
    return at


def run(match_dir):
    """-> warnings. A failure is a warning, never raised: the match is still published without its broadcast graphics."""
    try:
        return _run(match_dir)
    except Exception as err:
        return [f"broadcast rundown failed: {type(err).__name__}: {err}"]


def _run(match_dir):
    events = read_jsonl(os.path.join(match_dir, "interpret", "events_enriched.jsonl"))
    rows = read_jsonl(os.path.join(match_dir, "tracking.jsonl"))
    thr = read_json(os.path.join(match_dir, "interpret", "meta.json"))["thresholds"]["sprint_speed_m_s"]
    clock = {r["t_s"]: r["clock_s"] for r in rows}
    sprints = [{**s, "team": team_of(s["player_id"]), "clock_s": clock[s["t_s"]]} for s in physical.sprint_runs(rows, thr)]
    meta = read_json(os.path.join(match_dir, "meta.json"))
    out = rundown.build(events, sprints, _travelled(rows), meta.get("match_id"), _net_at(rows, meta["pitch"]["length_m"] / 2))
    path = os.path.join(match_dir, "render", "broadcast", "rundown.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_atomic(path, json.dumps(out, ensure_ascii=False, indent=1))
    return []
