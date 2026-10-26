"""Train the engine xG, xPass and VAEP models on the synthetic datasets (data/datasets/). Loading them back is tacticai.interpret.application.models."""
import json
import os

import numpy as np

from ..interpret.domain import logistic as lg, vaep
from ..interpret.application.models import DERIVED, _predict, _vec
from ..interpret.domain.shots import NOT_SHOT_STATES, SHOT_MAX_ABS_Y_M, SHOT_MIN_SPEED, is_shot

FEATURES = ["dist_goal_center_m", "visible_goal_angle_deg", "defenders_in_cone", "nearest_defender_m", "defenders_within_3m",
            "gk_dist_to_shot_line_m", "gk_off_line_m", "header"]
BASELINE = FEATURES[:2]
L2S = (0.1, 1.0, 10.0)
NOTE = "probability of goal in the tacticAI synthetic engine; not real-football xG"


def _fit(rows, names, l2, label="goal"):
    """-> model dict (features, mean, std, weights, intercept, l2, fill) fitted on rows."""
    base = [n for n in names if n not in DERIVED]
    fill = {n: float(np.mean([k[n] for k in rows if k[n] is not None])) for n in base}
    X, mean, std = lg.standardize([_vec(k, names, fill) for k in rows])
    w, b = lg.fit(X, [k[label] for k in rows], l2)
    return {"features": names, "mean": mean.tolist(), "std": std.tolist(), "weights": w.tolist(), "intercept": b, "l2": l2, "fill": fill}


def _metrics(p, y):
    return {"n": len(y), "goals": int(sum(y)), "brier": lg.brier(p, y), "log_loss": lg.log_loss(p, y), "auc": lg.auc(p, y)}


def _train(train, names, label="goal"):
    """Chooses l2 by 5-fold CV on train jobs (fold = (job_seed // 5) % 5, log loss) -> model fitted on all train rows."""
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


def _fit_write(rows, features, base, label, out_path, head, extra, note):
    """Split by job_seed % 5 (0 = test), fit model + baseline, write the model JSON (keys: head, the fit, extra, metrics...) -> model dict."""
    train_rows, test = [k for k in rows if k["job_seed"] % 5], [k for k in rows if k["job_seed"] % 5 == 0]
    m, cv = _train(train_rows, features, label)
    bm, _ = _train(train_rows, base, label)
    yt = [k[label] for k in test]
    p, bp = _predict(m, test), _predict(bm, test)
    model = {**head, **m, **extra, "metrics": {"test": _metrics(p, yt), "baseline": {**_metrics(bp, yt), "features": bm["features"], "l2": bm["l2"]}},
             "cv_log_loss": {str(k): v for k, v in cv.items()}, "calibration": lg.calibration(p, yt),
             "n_train": len(train_rows), "n_test": len(test), "note": note}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(model, f, indent=1)
    return model


def train(data_dir, out_path):
    with open(os.path.join(data_dir, "kicks.jsonl")) as f:
        rows = [k for k in map(json.loads, f) if is_shot(k)]
    head = {"id": "xg_v1", "kind": "logistic", "trained_on": "shots_v2",
            "shot_rule": {"min_speed_m_s": SHOT_MIN_SPEED, "max_abs_projected_y_m": SHOT_MAX_ABS_Y_M, "excluded_outcome": "kept", "excluded_game_states": list(NOT_SHOT_STATES)}}
    return _fit_write(rows, FEATURES, BASELINE, "goal", out_path, head, {}, NOTE)


XPASS_FEATURES = ["length_m", "progressive_m", "start_x_att", "passer_pressure", "opponents_near_line", "nearest_opponent_to_receiver_m", "lines_broken",
                 "log1p_nearest_opp", "nearest_opp_cap5", "length_sq_100", "log1p_length"]
XPASS_NOTE = "probability of completing the pass in the tacticAI synthetic engine"


def train_xpass(data_dir, out_path):
    """Same recipe as xG on passes.jsonl (label `complete`, features known at release); the metrics key `goals` counts completed passes."""
    with open(os.path.join(data_dir, "passes.jsonl")) as f:
        rows = [{**k, "job_seed": int(k["match_id"].rsplit("_", 1)[1])} for k in map(json.loads, f)]  # match_id = recipe_<kind>_<job seed>
    head = {"id": "xpass_v1", "kind": "logistic", "trained_on": "v3"}  # nulls are filled with the train mean
    return _fit_write(rows, XPASS_FEATURES, ["length_m"], "complete", out_path, head, {"derived": {n: DERIVED[n][0] for n in XPASS_FEATURES if n in DERIVED}}, XPASS_NOTE)


VAEP_NOTE = "VAEP of the tacticAI synthetic engine (probability of scoring / conceding within the next 10 actions); not real-football VAEP"


def train_vaep(data_dir, out_path):
    """Two logistic models (scores, concedes) on actions.jsonl: L2 by grouped CV over jobs as in train(), test = job_seed % 5 == 0, baseline = start xa/ya of a_i."""
    with open(os.path.join(data_dir, "actions.jsonl")) as f:
        rows = [json.loads(line) for line in f]
    train_rows, test = [k for k in rows if k["job_seed"] % 5], [k for k in rows if k["job_seed"] % 5 == 0]
    model = {"id": "vaep_v1", "kind": "logistic", "trained_on": os.path.basename(os.path.normpath(data_dir)), "features": vaep.FEATURES,
             "n_train": len(train_rows), "n_test": len(test), "note": VAEP_NOTE}
    for label in ("scores", "concedes"):
        m, cv = _train(train_rows, vaep.FEATURES, label)
        bm, _ = _train(train_rows, vaep.BASELINE, label)
        yt = [k[label] for k in test]
        p, bp = _predict(m, test), _predict(bm, test)
        met, bmet = _metrics(p, yt), _metrics(bp, yt)
        model[label] = {**m, "metrics": {"test": met, "baseline": {**bmet, "features": bm["features"], "l2": bm["l2"]}},
                        "beats_baseline": bool((met["auc"] or 0) > (bmet["auc"] or 0) and met["brier"] < bmet["brier"]),
                        "cv_log_loss": {str(k): v for k, v in cv.items()}, "calibration": lg.calibration(p, yt)}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(model, f, indent=1)
    return model
