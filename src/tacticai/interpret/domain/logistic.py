"""Pure L2 logistic regression (IRLS/Newton) and probability metrics. numpy only."""
import numpy as np


def standardize(X):
    """-> (Xs, mean, std); a constant column gets std 1."""
    X = np.asarray(X, float)
    m, s = X.mean(0), X.std(0)
    s = np.where(s > 0, s, 1.0)
    return (X - m) / s, m, s


def _sig(z):
    return 1 / (1 + np.exp(-np.clip(z, -35, 35)))


def fit(X, y, l2=1.0, max_iter=50, tol=1e-8):
    """-> (w, b): intercept b is not penalised."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    A = np.hstack([np.ones((len(X), 1)), X])
    pen = np.diag([0.0] + [l2] * X.shape[1])
    beta = np.zeros(A.shape[1])
    for _ in range(max_iter):
        p = _sig(A @ beta)
        step = np.linalg.solve(A.T @ (A * (p * (1 - p))[:, None]) + pen + 1e-12 * np.eye(len(beta)), A.T @ (p - y) + pen @ beta)
        beta -= step
        if np.abs(step).max() < tol:
            break
    return beta[1:], float(beta[0])


def predict(w, X, b=0.0):
    return _sig(np.asarray(X, float) @ np.asarray(w, float) + b)


def brier(p, y):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def log_loss(p, y):
    p, y = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12), np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(p, y):
    """Rank-based (Mann-Whitney) with average ranks for ties; None if one class is missing."""
    p, y = np.asarray(p, float), np.asarray(y, bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if not n1 or not n0:
        return None
    order = np.argsort(p, kind="mergesort")
    ps, ranks = p[order], np.empty(len(p))
    i = 0
    while i < len(p):
        j = i
        while j + 1 < len(p) and ps[j + 1] == ps[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def calibration(p, y, bins=10):
    """Equal-width probability bins over [0, 1] (empty bins omitted) -> [{bin_lo, bin_hi, n, mean_p, rate}]."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return [{"bin_lo": k / bins, "bin_hi": (k + 1) / bins, "n": int(m.sum()), "mean_p": float(p[m].mean()), "rate": float(y[m].mean())}
            for k in range(bins) if (m := idx == k).any()]
