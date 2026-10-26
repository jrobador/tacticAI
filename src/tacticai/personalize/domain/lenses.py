"""Lens table. Thresholds, slots and bonuses live here together so they can be tuned while watching the demo."""

LANGS = ("en", "es")
CLUBS = ("neutral", "home", "away")
TEXT_LENSES = ("analyst", "fan", "first_match")  # the lenses that own a text; broadcast and one_metric use the analyst's

CLUB_BONUS = 0.15
PLAYER_BONUS = 0.25

# threshold: minimum priority to appear; slots: overlays on screen at once; text: which text lens writes the copy
LENSES = {
    "analyst": {"threshold": 0.3, "slots": ("bottom_left", "top_right", "bottom_right"), "text": "analyst", "all_metrics": True},
    "fan": {"threshold": 0.6, "slots": ("bottom_left",), "text": "fan", "all_metrics": False},
    "first_match": {"threshold": 0.5, "slots": ("bottom_left",), "text": "first_match", "all_metrics": False},
    "broadcast": {"threshold": 0.3, "slots": (), "text": "analyst", "all_metrics": True},  # queue, no slots
    "one_metric": {"threshold": 0.2, "slots": ("bottom_left",), "text": "analyst", "all_metrics": False},
}

# main metric per kind (and subtype where it changes); None = the insight has no main metric (a goal without a shot)
MAIN_METRIC = {
    ("lines_broken", None): "lines_broken",
    ("pressure_spell", "peak"): "value",
    ("pressure_spell", None): "after",
    ("goal_or_chance", None): "xg",
    ("momentum_shift", "dominance"): "mean_momentum",
    ("momentum_shift", None): "after",
}


def main_metric(insight):
    name = MAIN_METRIC.get((insight["kind"], insight["subtype"])) or MAIN_METRIC.get((insight["kind"], None))
    return name if name in insight["metrics"] else None


def priority(insight, club="neutral", player=None):
    """clamp(importance + club bonus (insight of the chosen club) + player bonus (player in insight.players), 0, 1)."""
    bonus = (CLUB_BONUS if club in ("home", "away") and insight["team"] == club else 0.0) + (PLAYER_BONUS if player and player in insight["players"] else 0.0)
    return min(1.0, max(0.0, insight["importance"]["value"] + bonus))


def perspective(club, team):
    """neutral | own (insight of the chosen club) | opponent."""
    return "neutral" if club == "neutral" else "own" if team == club else "opponent"
