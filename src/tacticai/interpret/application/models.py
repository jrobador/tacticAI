"""Load the trained engine models (xG, xPass, VAEP) from their JSON files as callables. Training lives in tacticai.training.train_models."""
import json
import math

import numpy as np

from ..domain import logistic as lg

# derived features: name -> (description, f(row with nulls already filled)); stored by name in the model JSON
DERIVED = {
    "log1p_nearest_opp": ("log1p(nearest_opponent_to_receiver_m)", lambda r: math.log1p(r["nearest_opponent_to_receiver_m"])),
    "nearest_opp_cap5": ("min(nearest_opponent_to_receiver_m, 5.0)", lambda r: min(r["nearest_opponent_to_receiver_m"], 5.0)),
    "length_sq_100": ("length_m ** 2 / 100", lambda r: r["length_m"] ** 2 / 100),
    "log1p_length": ("log1p(length_m)", lambda r: math.log1p(r["length_m"])),
}


def _vec(k, names, fill):
    """Feature vector of one kick dict; nulls take the fill value, derived features are computed from the filled row."""
    r = {**k, **{n: f for n, f in fill.items() if k.get(n) is None}}
    return [DERIVED[n][1](r) if n in DERIVED else float(r[n]) for n in names]


def _predict(m, rows):
    X = (np.array([_vec(k, m["features"], m["fill"]) for k in rows]) - m["mean"]) / m["std"]
    return lg.predict(m["weights"], X, m["intercept"])


def load_xg(path):
    """-> callable f(kick_dict) -> P(goal) with .info = {id, trained_on, kind, features}."""
    with open(path) as f:
        m = json.load(f)

    def xg(k):
        return float(_predict(m, [k])[0])
    xg.info = {k: m[k] for k in ("id", "trained_on", "kind", "features")}
    return xg


def load_vaep(path):
    """-> callable f(feature_dict) -> (P_scores, P_concedes) with .info = {id, trained_on, kind, features, metrics, beats_baseline} (the last two per label).
    None when either head does not beat the baseline (no ratings are published then)."""
    with open(path) as f:
        m = json.load(f)
    if not (m["scores"]["beats_baseline"] and m["concedes"]["beats_baseline"]):
        return None

    def vaep_model(k):
        return float(_predict(m["scores"], [k])[0]), float(_predict(m["concedes"], [k])[0])
    vaep_model.info = {**{k: m[k] for k in ("id", "trained_on", "kind", "features")}, "metrics": {k: m[k]["metrics"] for k in ("scores", "concedes")},
                       "beats_baseline": {k: m[k]["beats_baseline"] for k in ("scores", "concedes")}}
    return vaep_model
