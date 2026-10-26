import numpy as np
import pytest

from tacticai.interpret.domain.logistic import auc, brier, calibration, fit, log_loss, predict, standardize
from tacticai.interpret.domain.shots import is_shot

K = dict(speed_m_s=20.0, projected_y_at_goal_m=3.0, outcome="saved", game_state="open_play")


def test_is_shot():
    assert is_shot(K)
    assert is_shot({**K, "speed_m_s": 18.0, "projected_y_at_goal_m": -7.5})
    assert not is_shot({**K, "speed_m_s": 17.9})
    assert not is_shot({**K, "projected_y_at_goal_m": 7.6})
    assert not is_shot({**K, "outcome": "kept"})
    assert all(not is_shot({**K, "game_state": s}) for s in ("throw_in", "goal_kick", "kick_off"))


def test_fit_recovers_coefficients():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(20000, 2))
    y = rng.random(20000) < 1 / (1 + np.exp(-(0.5 + 1.5 * X[:, 0] - 1.0 * X[:, 1])))
    Xs, m, s = standardize(X)
    w, b = fit(Xs, y, l2=0.1)
    assert w[0] == pytest.approx(1.5, abs=0.15) and w[1] == pytest.approx(-1.0, abs=0.15) and b == pytest.approx(0.5, abs=0.1)
    assert auc(predict(w, Xs, b), y) > 0.8


def test_standardize_constant_column():
    Xs, m, s = standardize([[1, 5], [3, 5]])
    assert Xs.tolist() == [[-1, 0], [1, 0]] and s.tolist() == [1, 1]


def test_metrics():
    p, y = [0.9, 0.1, 0.5, 0.5], [1, 0, 1, 0]
    assert brier(p, y) == pytest.approx((0.01 + 0.01 + 0.25 + 0.25) / 4)
    assert log_loss(p, y) == pytest.approx(-(2 * np.log(0.9) + 2 * np.log(0.5)) / 4)
    assert log_loss([0.0], [1]) == pytest.approx(-np.log(1e-12))
    assert auc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == 0.75
    assert auc([0.5, 0.5], [0, 1]) == 0.5 and auc([0.5], [1]) is None
    c = calibration(p, y, bins=10)
    assert [r["n"] for r in c] == [1, 2, 1] and c[1]["rate"] == 0.5 and c[2]["bin_lo"] == 0.9
