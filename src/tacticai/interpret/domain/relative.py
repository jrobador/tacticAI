"""Match-relative references: possession phases, non-overlapping 5 s windows, quantiles, percentile and bands with the guards.
Phase of a team per row = 'own' / 'opp' from the stable owner of that row, 'loose' when open play has no owner, None outside open play. One possession definition: loose rows are never possession."""
import math

from .physical import _quantile, is_open

WINDOW_S, MIN_WINDOWS = 5.0, 4
FLAT_IQR_M, FLAT_IQR_PRESSURE, FLAT_IQR_PPDA = 1.0, 0.05, 1.0  # dispersion below this (IQR) is flat: no bands (PPDA in passes per recovery)


def rounded(o, n=3):
    """Recursively round floats so outputs are ready to cite."""
    if isinstance(o, float):
        return round(o, n)
    if isinstance(o, dict):
        return {k: rounded(v, n) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [rounded(v, n) for v in o]
    return o


def step(rows):
    """Frame step in seconds from the first consecutive-frame pair (0.1 when none)."""
    return next((b["t_s"] - a["t_s"] for a, b in zip(rows, rows[1:]) if b["frame_index"] == a["frame_index"] + 1), 0.1)


def durations(rows):
    """Seconds each row lasts: gap to the next row when this one is open play and the next is the following frame, else 0 (sums to physical.open_play_seconds)."""
    return [rows[i + 1]["t_s"] - r["t_s"] if is_open(r) and i + 1 < len(rows) and rows[i + 1]["frame_index"] == r["frame_index"] + 1 else 0.0
            for i, r in enumerate(rows)]


def phases(rows, owners, team):
    """Per row: 'own' / 'opp' (stable owner of that row), 'loose' (open play, no owner) or None (not open play)."""
    return [None if not is_open(r) else "loose" if not owners[i] else "own" if owners[i][0] == team else "opp" for i, r in enumerate(rows)]


def flag_runs(rows, flags, min_s=0.0):
    """[(i0, i1)] maximal runs of True flags over consecutive-frame rows spanning >= min_s (last t_s - first t_s + step)."""
    out, st, s = [], None, step(rows)

    def close(a, b):
        if rows[b]["t_s"] - rows[a]["t_s"] + s >= min_s - 1e-9:
            out.append((a, b))

    for i, f in enumerate(flags):
        if st is not None and not (f and rows[i]["frame_index"] == rows[i - 1]["frame_index"] + 1):
            close(st, i - 1)
            st = None
        if f and st is None:
            st = i
    if st is not None:
        close(st, len(rows) - 1)
    return out


def windows(rows, phs, want=None, window_s=WINDOW_S):
    """[(i0, i1)] complete non-overlapping windows: inside each run of consecutive rows with the same phase (only `want` when given) a window closes once it spans
    window_s; the remainder of a run is a fragment and is dropped (descriptive evidence only, never a reference)."""
    out, s, n, i = [], step(rows), len(rows), 0
    while i < n:
        if phs[i] is None or (want and phs[i] != want) or (not want and phs[i] == "loose"):
            i += 1
            continue
        j = i
        while j + 1 < n and phs[j + 1] == phs[i] and rows[j + 1]["frame_index"] == rows[j]["frame_index"] + 1:
            j += 1
        a = i
        for k in range(i, j + 1):
            if rows[k]["t_s"] - rows[a]["t_s"] + s >= window_s - 1e-9:
                out.append((a, k))
                a = k + 1
        i = j + 1
    return out


def window_values(rows, phs, series, want=None, window_s=WINDOW_S):
    """Mean of series ({row index: value}) per complete window; a window needs a value in every one of its rows (full effective coverage), else it is dropped
    (a fragment or partly covered window is descriptive evidence only, never a reference)."""
    out = []
    for a, b in windows(rows, phs, want, window_s):
        if all(i in series for i in range(a, b + 1)):
            out.append(sum(series[i] for i in range(a, b + 1)) / (b - a + 1))
    return out


def reference(values, flat_iqr):
    """Reference of window values: n_windows, sufficient, reason and (only when sufficient) median, q25, q75, max, values."""
    n = len(values)
    if n < MIN_WINDOWS:
        return {"n_windows": n, "sufficient": False, "reason": f"fewer than {MIN_WINDOWS} complete 5 s reference windows ({n})"}
    q25, med, q75 = (_quantile(values, q) for q in (0.25, 0.5, 0.75))
    if q75 - q25 < flat_iqr:
        return {"n_windows": n, "sufficient": False, "reason": f"flat dispersion (IQR {q75 - q25:.3f} < {flat_iqr})"}
    return {"n_windows": n, "sufficient": True, "reason": None, "median": med, "q25": q25, "q75": q75, "max": max(values), "values": values}


def place(value, ref):
    """Public relative block of `value` against `ref`: quantiles, percentile (mid-rank), rank among windows (1 = highest) and band; None when ref is insufficient."""
    out = {"n_windows": ref["n_windows"], "median": None, "q25": None, "q75": None, "max": None, "percentile": None, "rank": None, "band": None, "relative_reason": None}
    if not ref["sufficient"]:
        return {**out, "relative_reason": ref["reason"]}
    if value is None:
        return {**out, "relative_reason": "no value"}
    v = ref["values"]
    close = [math.isclose(w, value, rel_tol=1e-9, abs_tol=1e-9) for w in v]  # window means differ by ~1e-15 between Python versions (sum() compensation)
    lo, eq = sum(w < value and not c for w, c in zip(v, close)), sum(close)
    return {**out, **{k: ref[k] for k in ("median", "q25", "q75", "max")}, "percentile": 100 * (lo + eq / 2) / len(v), "rank": 1 + sum(w > value and not c for w, c in zip(v, close)),
            "band": "high_relative" if value > ref["q75"] else "low_relative" if value < ref["q25"] else "typical"}
