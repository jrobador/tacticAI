"""Player Focus heatmaps: <match>/tracking.jsonl + roster.json -> <match>/render/heatmaps.json."""
import json
import os

from ...interpret.domain.physical import is_open

X_BINS, Y_BINS = 16, 12


def _cell(v, lo, hi, bins):
    return min(bins - 1, max(0, int((v - lo) / (hi - lo) * bins)))


def compute(rows, roster_ids, length_m, width_m):
    """rows: iterable of tracking rows in order. -> the heatmaps dict."""
    xlo, xhi, ylo, yhi = -length_m / 2, length_m / 2, -width_m / 2, width_m / 2
    secs = {pid: 0.0 for pid in roster_ids}
    grids = {}
    prev = None
    for b in rows:
        a, prev = prev, b
        if a is None or b["frame_index"] != a["frame_index"] + 1 or a["period"] != b["period"] or not (is_open(a) and is_open(b)):
            continue
        dt = b["t_s"] - a["t_s"]
        on_b = {p["player_id"] for p in b["players"] if p.get("on_pitch")}
        for p in a["players"]:
            pid = p["player_id"]
            if not p.get("on_pitch") or pid not in on_b:
                continue
            g = grids.setdefault(pid, [[0.0] * Y_BINS for _ in range(X_BINS)])
            g[_cell(p["x"], xlo, xhi, X_BINS)][_cell(p["y"], ylo, yhi, Y_BINS)] += dt
            secs[pid] = secs.get(pid, 0.0) + dt
    players = {pid: {"eligible_s": round(s, 3), "grid": [[round(c, 3) for c in r] for r in grids[pid]] if s > 0 else None} for pid, s in sorted(secs.items())}
    return {"heatmap_version": 1, "x_bins": X_BINS, "y_bins": Y_BINS, "bounds": {"x": [round(xlo, 3), round(xhi, 3)], "y": [round(ylo, 3), round(yhi, 3)]},
            "unit": "s", "players": players}


def _tracking(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def run(match_dir):
    def load(name):
        with open(os.path.join(match_dir, name), encoding="utf-8") as f:
            return json.load(f)
    pitch = load("meta.json")["pitch"]
    ids = [p["player_id"] for p in load("roster.json")["players"]]
    out = compute(_tracking(os.path.join(match_dir, "tracking.jsonl")), ids, pitch["length_m"], pitch["width_m"])
    os.makedirs(os.path.join(match_dir, "render"), exist_ok=True)
    path = os.path.join(match_dir, "render", "heatmaps.json")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(out, f)
    os.replace(path + ".tmp", path)
    return []
