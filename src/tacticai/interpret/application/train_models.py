"""Train the engine xG model on data/datasets/shots_v2 (kicks inside the shot rule, split by job) and load it back as a callable f(kick) -> probability."""
import json
import math
import os

import numpy as np

from ..domain import logistic as lg
from ..domain.shots import NOT_SHOT_STATES, SHOT_MAX_ABS_Y_M, SHOT_MIN_SPEED, is_shot

FEATURES = ["dist_goal_center_m", "visible_goal_angle_deg", "defenders_in_cone", "nearest_defender_m", "defenders_within_3m",
            "gk_dist_to_shot_line_m", "gk_off_line_m", "header"]
BASELINE = FEATURES[:2]
GK_FEATURES = ("gk_dist_to_shot_line_m", "gk_off_line_m")
L2S = (0.1, 1.0, 10.0)
NOTE = "probability of goal in the tacticAI synthetic engine; not real-football xG"


# derived features: name -> (description, f(row with nulls already filled)); stored by name in the model JSON
DERIVED = {
    "log1p_nearest_opp": ("log1p(nearest_opponent_to_receiver_m)", lambda r: math.log1p(r["nearest_opponent_to_receiver_m"])),
    "nearest_opp_cap5": ("min(nearest_opponent_to_receiver_m, 5.0)", lambda r: min(r["nearest_opponent_to_receiver_m"], 5.0)),
    "length_sq_100": ("length_m ** 2 / 100", lambda r: r["length_m"] ** 2 / 100),
    "log1p_length": ("log1p(length_m)", lambda r: math.log1p(r["length_m"])),
}


def _vec(k, names, fill):
    """Feature vector of one kick dict; nulls take the fill value, derived features are computed from the filled row, gk_missing is 1 when the opponent has no GK."""
    r = {**k, **{n: f for n, f in fill.items() if k.get(n) is None}}
    v = [DERIVED[n][1](r) if n in DERIVED else float(r[n]) for n in names if n != "gk_missing"]
    return v + [float(k["gk_dist_to_shot_line_m"] is None)] if "gk_missing" in names else v


def _fit(rows, names, l2, label="goal"):
    """-> model dict (features, mean, std, weights, intercept, l2, fill) fitted on rows."""
    base = [n for n in names if n != "gk_missing" and n not in DERIVED]
    fill = {n: float(np.mean([k[n] for k in rows if k[n] is not None])) for n in base}
    X, mean, std = lg.standardize([_vec(k, names, fill) for k in rows])
    w, b = lg.fit(X, [k[label] for k in rows], l2)
    return {"features": names, "mean": mean.tolist(), "std": std.tolist(), "weights": w.tolist(), "intercept": b, "l2": l2, "fill": fill}


def _predict(m, rows):
    X = (np.array([_vec(k, m["features"], m["fill"]) for k in rows]) - m["mean"]) / m["std"]
    return lg.predict(m["weights"], X, m["intercept"])


def _metrics(p, y):
    return {"n": len(y), "goals": int(sum(y)), "brier": lg.brier(p, y), "log_loss": lg.log_loss(p, y), "auc": lg.auc(p, y)}


def _train(train, names, with_gk_flag, label="goal"):
    """Chooses l2 by 5-fold CV on train jobs (fold = (job_seed // 5) % 5, log loss) -> model fitted on all train rows."""
    names = names + (["gk_missing"] if with_gk_flag else [])
    y = [k[label] for k in train]
    folds = np.array([(k["job_seed"] // 5) % 5 for k in train])
    cv = {}
    for l2 in L2S:
        p = np.zeros(len(train))
        for f in range(5):
            tr, te = [k for k, g in zip(train, folds) if g != f], folds == f
            p[te] = _predict(_fit(tr, names, l2, label), [k for k, g in zip(train, folds) if g == f])
        cv[l2] = lg.log_loss(p, y)
    best = min(cv, key=cv.get)
    return _fit(train, names, best, label), cv


def train(data_dir, out_path):
    with open(os.path.join(data_dir, "kicks.jsonl")) as f:
        rows = [k for k in map(json.loads, f) if is_shot(k)]
    train_rows, test = [k for k in rows if k["job_seed"] % 5], [k for k in rows if k["job_seed"] % 5 == 0]
    flag = any(k[n] is None for k in rows for n in GK_FEATURES)
    m, cv = _train(train_rows, FEATURES, flag)
    bm, bcv = _train(train_rows, BASELINE, False)
    yt = [k["goal"] for k in test]
    p, bp = _predict(m, test), _predict(bm, test)
    model = {"id": "xg_v1", "kind": "logistic", "trained_on": "shots_v2",
             "shot_rule": {"min_speed_m_s": SHOT_MIN_SPEED, "max_abs_projected_y_m": SHOT_MAX_ABS_Y_M, "excluded_outcome": "kept", "excluded_game_states": list(NOT_SHOT_STATES)},
             **m, "metrics": {"test": _metrics(p, yt), "baseline": {**_metrics(bp, yt), "features": bm["features"], "l2": bm["l2"]}},
             "cv_log_loss": {str(k): v for k, v in cv.items()}, "calibration": lg.calibration(p, yt),
             "n_train": len(train_rows), "n_test": len(test), "note": NOTE}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(model, f, indent=1)
    return model


XPASS_FEATURES = ["length_m", "progressive_m", "start_x_att", "passer_pressure", "opponents_near_line", "nearest_opponent_to_receiver_m", "lines_broken",
                 "log1p_nearest_opp", "nearest_opp_cap5", "length_sq_100", "log1p_length"]
XPASS_NOTE = "probability of completing the pass in the tacticAI synthetic engine"


def train_xpass(data_dir, out_path):
    """Same recipe as xG on passes.jsonl (label `complete`, features known at release); the metrics key `goals` counts completed passes."""
    with open(os.path.join(data_dir, "passes.jsonl")) as f:
        rows = [{**k, "job_seed": int(k["match_id"].rsplit("_", 1)[1])} for k in map(json.loads, f)]  # match_id = recipe_<kind>_<job seed>
    train_rows, test = [k for k in rows if k["job_seed"] % 5], [k for k in rows if k["job_seed"] % 5 == 0]
    m, cv = _train(train_rows, XPASS_FEATURES, False, "complete")  # nulls are filled with the train mean
    bm, _ = _train(train_rows, ["length_m"], False, "complete")
    yt = [k["complete"] for k in test]
    p, bp = _predict(m, test), _predict(bm, test)
    model = {"id": "xpass_v1", "kind": "logistic", "trained_on": "v3", **m, "derived": {n: DERIVED[n][0] for n in XPASS_FEATURES if n in DERIVED},
             "metrics": {"test": _metrics(p, yt), "baseline": {**_metrics(bp, yt), "features": bm["features"], "l2": bm["l2"]}},
             "cv_log_loss": {str(k): v for k, v in cv.items()}, "calibration": lg.calibration(p, yt),
             "n_train": len(train_rows), "n_test": len(test), "note": XPASS_NOTE}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(model, f, indent=1)
    return model


def load_xg(path):
    """-> callable f(kick_dict) -> P(goal) with .info = {id, trained_on, kind, features}."""
    with open(path) as f:
        m = json.load(f)

    def xg(k):
        return float(_predict(m, [k])[0])
    xg.info = {k: m[k] for k in ("id", "trained_on", "kind", "features")}
    return xg


load_xpass = load_xg  # same JSON structure; the callable takes a pass-feature dict
