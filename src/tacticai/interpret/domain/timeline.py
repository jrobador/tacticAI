"""Pure timeline (contract interpret/timeline.jsonl): N_WINDOWS equal parts of open-play time (cumulative consecutive-frame seconds, like physical.open_play_seconds)."""
import math

from .frame import x_att
from .physical import is_open
from .pressure import team_pressure
from .sequences import xg_total

N_WINDOWS, SMOOTH_WINDOWS = 18, 3
MOMENTUM_WEIGHTS = {"xg": 3.0, "final_third_entries": 0.25, "possession_share": 1.0}


def _window_of(rows, n):
    """{row index: window} for open-play rows; a row's time is the cumulative open-play seconds before it."""
    cum, c = {}, 0.0
    for i, r in enumerate(rows):
        if is_open(r):
            cum[i] = c
            if i + 1 < len(rows) and rows[i + 1]["frame_index"] == r["frame_index"] + 1:
                c += rows[i + 1]["t_s"] - r["t_s"]
    return {i: min(n - 1, int(n * v / c)) if c else 0 for i, v in cum.items()}


def _entries(rows, owners, ids, team, third_m):
    return sum(1 for i in ids if i and is_open(rows[i - 1]) and rows[i]["frame_index"] == rows[i - 1]["frame_index"] + 1 and owners[i] and owners[i][0] == team
               and x_att(rows[i - 1]["ball"]["x"], team) < third_m <= x_att(rows[i]["ball"]["x"], team))


def timeline(rows, owners, events, meta, xg_by_event=None, n_windows=N_WINDOWS):
    """-> list of window dicts. xg_by_event: {index into events: xg} (None = no model); a team's window xg is null without a model or without a scored shot in the window (momentum reads that as 0). possession_share is None when the window has no owner row."""
    groups = {}
    for i, w in sorted(_window_of(rows, n_windows).items()):
        groups.setdefault(w, []).append(i)
    keys, third_m = sorted(groups), meta["pitch"]["length_m"] / 6
    starts = [rows[groups[w][0]]["t_s"] for w in keys]
    out = []
    for k, w in enumerate(keys):
        ids, t0, t1 = groups[w], starts[k], starts[k + 1] if k + 1 < len(keys) else None
        first, last = rows[ids[0]], rows[ids[-1]]
        owned = [owners[i][0] for i in ids if owners[i]]
        rec = {"window": k, "start_t_s": first["t_s"], "end_t_s": last["t_s"], "start_clock_s": first["clock_s"], "end_clock_s": last["clock_s"], "period": first["period"]}
        for t in ("home", "away"):
            rec[t] = {"possession_share": owned.count(t) / len(owned) if owned else None, "pressure": team_pressure(rows, owners, t, t0, t1),
                      "xg": xg_total([xg_by_event.get(j) for j, e in enumerate(events) if e["type"] == "shot" and e["team"] == t and t0 <= e["t_s"] and (t1 is None or e["t_s"] < t1)]
                                    if xg_by_event is not None else [], xg_by_event is not None),
                      "final_third_entries": _entries(rows, owners, ids, t, third_m)}
        out.append(rec)
    w = MOMENTUM_WEIGHTS
    raw = [math.tanh(w["xg"] * ((r["home"]["xg"] or 0.0) - (r["away"]["xg"] or 0.0)) + w["final_third_entries"] * (r["home"]["final_third_entries"] - r["away"]["final_third_entries"])
                     + w["possession_share"] * ((r["home"]["possession_share"] or 0) - (r["away"]["possession_share"] or 0))) for r in out]
    h = SMOOTH_WINDOWS // 2
    for i, r in enumerate(out):
        near = raw[max(0, i - h):i + h + 1]
        r["momentum"] = sum(near) / len(near)
    return out
