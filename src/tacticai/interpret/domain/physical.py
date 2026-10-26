"""Pure physical metrics over contract tracking (open play, main camera, consecutive frames only). Speeds are the contract vx, vy
smoothed with a centred rolling mean of SMOOTH_S seconds (frames from the run's dt, window truncated at the ends of a run). Values are relative unless meta.calibration.physical_absolute."""
import math

from ...ingest.domain.contract import team_of

DEFAULT_PROJECTION = {"applies": True, "effective_play_s": 3300}
SMOOTH_S, SPRINT_MIN_S, SPRINT_Q = 0.5, 1.0, 0.9


def is_open(r):
    return r["game_state"] == "open_play" and r["camera"] == "main"


def open_play_seconds(rows):
    """Seconds of open play: t_s steps between consecutive-frame pairs whose first row is open play."""
    return sum(b["t_s"] - a["t_s"] for a, b in zip(rows, rows[1:]) if is_open(a) and b["frame_index"] == a["frame_index"] + 1)


def project(rate_per_min, meta):
    """Per-minute rate -> 90' total (rate per s x effective_play_s); None when the source's totals are already real."""
    p = meta.get("projection", DEFAULT_PROJECTION)
    return rate_per_min / 60 * p["effective_play_s"] if p["applies"] and rate_per_min is not None else None


def _dt(ts):
    return (ts[-1] - ts[0]) / (len(ts) - 1) if len(ts) > 1 else 0.0


def _smooth(v, ts):
    h = (round(SMOOTH_S / _dt(ts)) | 1) // 2 if len(ts) > 1 else 0  # odd window of ~SMOOTH_S
    return [sum(v[max(0, i - h):i + h + 1]) / len(v[max(0, i - h):i + h + 1]) for i in range(len(v))]


def _runs(rows, pick):
    """[(id, [(frame_index, t_s, x, y, speed)])]: maximal runs of consecutive open-play frames where pick(row) -> {id: (x, y, speed)} has the id."""
    done, cur, prev = [], {}, None
    for r in rows:
        op = is_open(r)
        ok = op and (prev is None or r["frame_index"] == prev + 1)
        got = pick(r) if op else {}
        for i in [i for i in cur if not (ok and i in got)]:
            done.append((i, cur.pop(i)))
        for i, (x, y, s) in got.items():
            cur.setdefault(i, []).append((r["frame_index"], r["t_s"], x, y, s))
        prev = r["frame_index"] if op else None
    return done + list(cur.items())


def _players(r):
    return {p["player_id"]: (p["x"], p["y"], math.hypot(p["vx"], p["vy"])) for p in r["players"] if p["on_pitch"]}


def _ball(r):
    b = r["ball"]
    return {"ball": (b["x"], b["y"], math.sqrt(b["vx"] ** 2 + b["vy"] ** 2 + b["vz"] ** 2))}


def _quantile(vals, q):
    s = sorted(vals)
    k = q * (len(s) - 1)
    lo = int(k)
    return s[lo] + (s[min(lo + 1, len(s) - 1)] - s[lo]) * (k - lo)


def _sprints(ts, speeds, thr):
    """Maximal stretches of speeds >= thr lasting >= SPRINT_MIN_S (last t_s - first t_s + frame dt)."""
    dt, n, start = _dt(ts), 0, None
    for i, s in enumerate(speeds + [-1]):
        if s >= thr:
            start = i if start is None else start
        elif start is not None:
            n += ts[i - 1] - ts[start] + dt >= SPRINT_MIN_S - 1e-9
            start = None
    return n


def _rank(vals):
    """{id: (rank 1 = highest, percentile 0..100)}."""
    n = len(vals)
    return {i: (1 + sum(w > v for w in vals.values()), 100 * sum(w < v for w in vals.values()) / (n - 1) if n > 1 else 100.0)
            for i, v in vals.items()}


def player_physical(rows, meta):
    """-> ({player_id: record}, sprint_threshold_m_s). Threshold = 90th percentile of all outfield smoothed open-play speeds (relative, not absolute).
    Record: team, role, distance_m, distance_per_min, top_speed_m_s, sprints (maximal stretches at/above the threshold lasting >= 1 s),
    sprints_per_min, top_speed_first/last_third_m_s (thirds of the player's own open-play time span), top_speed_drop_pct,
    distance_rank/top_speed_rank (1 = highest, GK included) and distance_percentile/top_speed_percentile (0..100)."""
    role = {p["player_id"]: p["role"] for r in rows for p in r["players"]}
    runs = [(i, run, _smooth([x[4] for x in run], [x[1] for x in run])) for i, run in _runs(rows, _players)]
    outf = [s for i, _, sm in runs if role[i] != "GK" for s in sm]
    thr = _quantile(outf, SPRINT_Q) if outf else None
    mins = open_play_seconds(rows) / 60
    acc = {}
    for i, run, sm in runs:
        a = acc.setdefault(i, {"dist": 0.0, "sprints": 0, "samples": []})
        a["dist"] += sum(math.dist(p[2:4], q[2:4]) for p, q in zip(run, run[1:]))
        a["sprints"] += _sprints([p[1] for p in run], sm, thr) if thr is not None else 0
        a["samples"] += [(p[1], s) for p, s in zip(run, sm)]
    out = {}
    for i, a in acc.items():
        ts = [t for t, _ in a["samples"]]
        t0, t1 = min(ts), max(ts)
        third = lambda k: max([s for t, s in a["samples"] if min(2, int(3 * (t - t0) / ((t1 - t0) or 1))) == k], default=None)
        first, last = third(0), third(2)
        out[i] = {"team": team_of(i), "role": role[i], "distance_m": a["dist"], "distance_per_min": a["dist"] / mins if mins else None,
                  "top_speed_m_s": max(s for _, s in a["samples"]), "sprints": a["sprints"], "sprints_per_min": a["sprints"] / mins if mins else None,
                  "top_speed_first_third_m_s": first, "top_speed_last_third_m_s": last,
                  "top_speed_drop_pct": 100 * (first - last) / first if first and last is not None else None}
    for key, rk in (("distance_m", "distance"), ("top_speed_m_s", "top_speed")):
        for i, (rank, pct) in _rank({i: p[key] for i, p in out.items()}).items():
            out[i][f"{rk}_rank"], out[i][f"{rk}_percentile"] = rank, pct
    return out, thr


def team_physical(players):
    """{team: {distance_m, distance_per_min, sprints}} summed over outfield players (GK excluded)."""
    out = {}
    for p in players.values():
        if p["role"] != "GK":
            t = out.setdefault(p["team"], {"distance_m": 0.0, "distance_per_min": 0.0, "sprints": 0})
            t["distance_m"] += p["distance_m"]
            t["distance_per_min"] += p["distance_per_min"] or 0.0
            t["sprints"] += p["sprints"]
    return out


def ball_speeds(rows, events, meta):
    """Ball top speed (smoothed 3D contract velocity, open play) and, per shot, the event's speed_m_s next to the RAW (unsmoothed) ball speed at its frame: smoothing would mix in the slow frames before the strike.
    `absolute` echoes meta.calibration.physical_absolute (default False): when False the values are relative."""
    at, raw = {}, {}
    for _, run in _runs(rows, _ball):
        for p, s in zip(run, _smooth([x[4] for x in run], [x[1] for x in run])):
            at[p[0]] = s
        raw.update((p[0], p[4]) for p in run)
    shots = [{"frame_index": e["frame_index"], "team": e["team"], "player_id": e["player_id"], "speed_m_s": e["speed_m_s"],
              "ball_speed_m_s": raw.get(e["frame_index"])} for e in events if e["type"] == "shot"]
    return {"top_speed_m_s": max(at.values(), default=None), "shots": shots,
            "absolute": meta.get("calibration", {}).get("physical_absolute", False)}
