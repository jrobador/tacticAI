"""Pure defensive-line detection and lines broken by passes. Lines = 1-D k-means (k = 3) of the opponent's outfield x_att, close lines merged."""
from statistics import median

from .frame import opponent, x_att

MERGE_M, MAX_ITER = 4.0, 20


def _kmeans(xs):
    """Sorted non-empty clusters (lists of values) of xs, centres initialised at min, median, max."""
    c, a = [min(xs), median(xs), max(xs)], None
    for _ in range(MAX_ITER):
        b = [min(range(3), key=lambda k: (abs(x - c[k]), k)) for x in xs]
        if b == a:
            break
        a = b
        c = [sum(x for x, j in zip(xs, b) if j == k) / b.count(k) if k in b else c[k] for k in range(3)]
    return [g for _, g in sorted((c[k], [x for x, j in zip(xs, a) if j == k]) for k in range(3) if k in a)]


def opponent_lines(row, team):
    """Sorted x_att centres (in `team`'s frame) of the opponent's outfield lines, 1-3 values ([] without outfield players)."""
    foe = opponent(team)
    xs = [x_att(p["x"], team) for p in row["players"] if p["on_pitch"] and p["role"] != "GK" and p["player_id"].startswith(foe)]
    if not xs:
        return []
    out = []
    for g in _kmeans(xs):
        if out and sum(g) / len(g) - sum(out[-1]) / len(out[-1]) < MERGE_M:
            out[-1] = out[-1] + g
        else:
            out.append(g)
    return [sum(g) / len(g) for g in out]


def lines_crossed(event, row):
    """Opponent lines the segment start -> end of a pass event crosses in `row`, whatever the outcome."""
    a, b = x_att(event["x"], event["team"]), x_att(event["end_x"], event["team"])
    return sum(a < c < b for c in opponent_lines(row, event["team"]))


def lines_broken(event, row):
    """Opponent lines a completed pass crosses (0 for any other event or outcome)."""
    return lines_crossed(event, row) if event["type"] == "pass" and event["outcome"] == "complete" else 0
