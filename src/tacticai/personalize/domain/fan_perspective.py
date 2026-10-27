"""Fan perspective: what a supporter of one club feels about each fact, and who is hero or villain for them. Pure code, no text.
The facts (fan_facts.py) carry no club; the Supporter agent writes from this perspective and the Fan judge checks it."""

#: Feeling of a supporter by (fact kind, relation of the acting side to their club). The acting side is fact["team"]: the scorer's,
#: the shooter's, the passer who lost it... Neutral supporters always feel "thrill". Mistakes depend on whether they were punished.
STANCE = {
    ("goal", "ours"): "celebrate", ("goal", "theirs"): "suffer",
    ("miss", "ours"): "anguish", ("miss", "theirs"): "relief",
    ("save", "ours"): "frustration", ("save", "theirs"): "relief",  # our shot kept out by their keeper / our keeper keeps theirs out
    ("mistake", "ours", True): "blame_ours", ("mistake", "ours", False): "scare",
    ("mistake", "theirs", True): "gloat", ("mistake", "theirs", False): "taunt",
    ("pinned", "ours"): "dominate", ("pinned", "theirs"): "under_siege",
    ("turn", "ours"): "uplift", ("turn", "theirs"): "worry",
    ("move", "ours"): "show_off", ("move", "theirs"): "humiliation",
    ("pass", "ours"): "enjoy", ("pass", "theirs"): "wary",
    ("carry", "ours"): "enjoy", ("carry", "theirs"): "wary",
    ("tackle", "ours"): "roar", ("tackle", "theirs"): "dismay",
    ("sprint", "ours"): "admire", ("sprint", "theirs"): "fear",
}
#: What each stance means, for the writer and the judge (one line each, no wording to copy).
MEANING = {
    "celebrate": "our goal: pure joy, worship whoever scored and set it up",
    "suffer": "their goal against us: pain, anger or disbelief; never celebrate it, never cheer their scorer",
    "anguish": "we missed a clear chance: agony at our own player's miss",
    "relief": "they had a clear chance or a shot that did not go in: relief, and praise for our keeper if he saved it",
    "frustration": "our shot was kept out by their keeper: frustration, grudging at their keeper",
    "blame_ours": "our player lost the ball and they punished us: blame him",
    "scare": "our player gave the ball away: a groan, and a scare if they went at our goal",
    "gloat": "their player gifted us the ball and we punished them: gloat",
    "taunt": "their player gave the ball away to us: taunt them, more so if we went at their goal",
    "enjoy": "we move the ball well: enjoy it, more so the further it goes or the more lines it breaks",
    "wary": "they move the ball against us: wary, nervous the further it goes",
    "roar": "one of ours won the ball back: roar for him, more so after a long, fast run into it",
    "dismay": "one of theirs took the ball off us: dismay at our player who lost it",
    "dominate": "we have them pinned back: swagger",
    "under_siege": "they have us pinned back: nerves, hold on",
    "uplift": "the game turned our way: belief",
    "worry": "the game turned their way: worry",
    "show_off": "we string passes together and they cannot get the ball: olé",
    "humiliation": "they keep the ball and we chase shadows: humiliation, anger at our team",
    "admire": "one of ours did something special: admire him",
    "fear": "one of theirs did something dangerous against us: fear, respect through gritted teeth",
    "thrill": "no side: react with excitement to exactly what happened in this play (who did what, and how), without taking a side",
}


def relation(side, club):
    """'ours', 'theirs' or 'neutral' for a side ('home'/'away') seen by a supporter of `club` ('home'/'away'/'neutral')."""
    return "neutral" if club == "neutral" else "ours" if side == club else "theirs"


def stance(fact, club):
    rel = relation(fact["team"], club)
    if rel == "neutral":
        return "thrill"
    key = (fact["kind"], rel, bool(fact.get("punished"))) if fact["kind"] == "mistake" else (fact["kind"], rel)
    return STANCE[key]


def player_roles(fact, team_of):
    """[{player_id, role, side}] of the players in a fact; `side` is the player's own side (a keeper is on the other side of the shot)."""
    return [{"player_id": pid, "role": role, "side": team_of[pid]} for role, pid in fact["players"].items()]


def result(winner, club):
    """'win', 'loss' or 'draw' for a club; for a neutral, 'draw' or 'decided'."""
    if winner is None:
        return "draw"
    return "decided" if club == "neutral" else "win" if winner == club else "loss"
