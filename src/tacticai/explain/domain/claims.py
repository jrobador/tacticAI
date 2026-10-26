"""Special claims an insight may carry; computed by code, never by an LLM."""


def goal_claims(team, score_before):
    """Claims of a goal by `team` given the score before it: first_goal (0-0), equaliser (leaves it level), go_ahead (was level or behind, now ahead)."""
    me, other = score_before[team], score_before["away" if team == "home" else "home"]
    diff_before = me - other
    out = []
    if me == 0 and other == 0:
        out.append("first_goal")
    if diff_before == -1:
        out.append("equaliser")
    if diff_before == 0:  # a goal adds exactly 1, so "ahead after" only from level
        out.append("go_ahead")
    return out


def pressure_claims(subtype):
    """A pressure peak is the team's match maximum."""
    return ["match_max"] if subtype == "peak" else []
