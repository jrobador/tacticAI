"""Pure event rules: football events from contract tracking frames, using positions only.
The ball owner is inferred from positions (`infer_owner`); the frame's `possession` field is never read.
Passes, tackles and carries use the stabilized owners (`stable_owners`); shots and goals use the raw last touch (`infer_owner`).
A touch too short to be stable still counts when the player strikes the ball (a first-time shot or pass): it is a reception."""
import math

from .clock import FRAME_S
from .contract import team_of

POST_M = 3.66  # goal post |y| (Laws of the Game)
DEFAULTS = dict(owner_radius_m=1.25, owner_max_z_m=1.0, tackle_dist_m=2.0, tackle_max_gap=2, shot_min_speed=18.0,
                shot_max_abs_y_m=7.5, shot_max_dist_m=40.0, shot_jump_m_s=5.0, shot_debounce=10, goal_lookahead=30,
                owner_min_frames=3, carry_min_m=5.0)
# carry_min_m: a player who moves the ball at least this far is carrying it, below it is a touch (the usual carry cut-off in event data)
NOT_SHOT_STATES = ("throw_in", "goal_kick", "kick_off")  # a kick from these restarts is not a shot


def infer_owner(f, radius_m, max_z_m):
    """(team, player_id) of the nearest on-pitch player to the ball in x/y if within radius_m and the ball is at most
    max_z_m high, else None (loose)."""
    b = f["ball"]
    if b["z"] > max_z_m:
        return None
    d, pid = min(((math.dist((p["x"], p["y"]), (b["x"], b["y"])), p["player_id"]) for p in f["players"] if p["on_pitch"]),
                 default=(math.inf, None))
    return (team_of(pid), pid) if d <= radius_m else None


def stable_owners(owners, min_frames, struck=None):
    """`owners` with every run of the same non-None owner shorter than min_frames replaced by None (loose ball); longer
    runs are kept as is, so an event stays at the run's first frame. Consecutive LINES count as consecutive frames: v1
    tracking has frame_index gaps (in-play frames only) and they are not treated as breaks. min_frames <= 1 is identity.
    `struck(j)` -> True when the ball was struck right after row j-1: a short run ending there is a first-time touch and is kept."""
    out, i = list(owners), 0
    while i < len(owners):
        j = i
        while j < len(owners) and owners[j] == owners[i]:
            j += 1
        if owners[i] is not None and j - i < min_frames and not (struck and j < len(owners) and struck(j)):
            out[i:j] = [None] * (j - i)
        i = j
    return out


def speed(r):
    return math.hypot(r["ball"]["vx"], r["ball"]["vy"])


def xy(r, pid):
    return next((p["x"], p["y"]) for p in r["players"] if p["player_id"] == pid)


def owners_of(rows, raw, th):
    """Stable owners aligned with rows (passes, tackles, carries, pressure): a first-time touch, where the ball leaves faster than it came, is a reception too."""
    return stable_owners(raw, th["owner_min_frames"], lambda j: speed(rows[j]) - speed(rows[j - 1]) >= th["shot_jump_m_s"])


def is_break(a, b):
    """Play stopped or a goal was scored between consecutive frames a -> b."""
    return (a["game_state"] == "open_play" and b["game_state"] != "open_play") or a["score"] != b["score"]


def is_pass(rows, owners, s, t):
    """True if the first owner after row s is team t (no decision -> False)."""
    for k in range(s + 1, len(rows)):
        if is_break(rows[k - 1], rows[k]):
            return False
        if owners[k]:
            return owners[k][0] == t
    return False


def teammate_next(raw, rows, i, t, shooter, n):
    """True if, within n rows after row i, a teammate of team t (not the shooter) touches the ball before the team scores."""
    for k in range(i + 1, min(i + 1 + n, len(rows))):
        if rows[k]["score"][t] > rows[i]["score"][t]:
            return False
        if raw[k] and raw[k][1] != shooter:
            return raw[k][0] == t
    return False


def kick_at(rows, i, touch, prev, last, who, half, min_speed, th):
    """Shared shot/kick trigger at row i (speed >= min_speed already checked) by `touch` (new vs `prev`): -> x of the goal kicked at, or None.
    Updates the per-team debounce state last/who on a hit."""
    r, t = rows[i], touch[0]
    v0, b, gx = speed(rows[i - 1]), r["ball"], half if t == "home" else -half
    if not (v0 < min_speed or speed(r) - v0 >= th["shot_jump_m_s"] or touch != prev and touch[1] != who.get(t)):
        return None
    if b["vx"] * gx <= 0 or abs(gx - b["x"]) > th["shot_max_dist_m"] or i - last[t] < th["shot_debounce"] and touch[1] == who.get(t):
        return None
    last[t], who[t] = i, touch[1]
    return gx


def extract(rows, th, length_m=108.8):
    half = length_m / 2
    raw = [infer_owner(r, th["owner_radius_m"], th["owner_max_z_m"]) for r in rows]  # shots, goals: one-touch shooters
    owners = owners_of(rows, raw, th)  # passes, tackles, carries: possession changes
    ev = []
    since = None  # row index where the current owner's spell with the ball began (carries)

    def carry(last, end_i):
        """The owner's spell from `since` to row end_i: a carry when he moved the ball carry_min_m or more."""
        t, pid, _ = last
        a, z = rows[since], rows[end_i]
        d = math.dist(xy(a, pid), xy(z, pid))
        if d >= th["carry_min_m"]:
            add(a, "carry", t, pid, a["ball"]["x"], a["ball"]["y"], end_x=round(z["ball"]["x"], 2), end_y=round(z["ball"]["y"], 2),
                distance_m=round(d, 2), duration_s=round(z["t_s"] - a["t_s"], 2))

    def add(r, typ, team, pid, x, y, **kw):
        ev.append(dict(type=typ, frame_index=r["frame_index"], t_s=r["t_s"], clock_s=r["clock_s"], period=r["period"],
                       team=team, player_id=pid, x=round(x, 2), y=round(y, 2), **kw))

    last = None  # (team, player_id, row index of last stabilized-owned row)
    touch = None  # (team, player_id) of the last raw owner before the current row
    last_shot, who = {"home": -10**9, "away": -10**9}, {}
    goal_shot = {}  # (team, row of the score change) -> the shot event that scored it
    for i, r in enumerate(rows):
        p, b = rows[i - 1] if i else None, r["ball"]
        pt = touch
        if i and raw[i - 1]:
            touch = raw[i - 1]
        if p and r["score"] != p["score"]:
            t = "home" if r["score"]["home"] > p["score"]["home"] else "away"
            scorer = touch[1] if touch and touch[0] == t else None
            if scorer is None:  # fall back to the goal shot of this score change (within goal_lookahead), else null
                scorer = goal_shot[t, i]["player_id"] if (t, i) in goal_shot else None
            add(r, "goal", t, scorer, b["x"], b["y"], scorer_id=scorer)
        if p and r["game_state"] != p["game_state"] and r["game_state"] != "open_play":
            m, j = r["game_state"], i
            while j + 1 < len(rows) and rows[j + 1]["game_state"] == m:
                j += 1
            q = rows[j]["ball"]
            _, pid = min((math.dist((pl["x"], pl["y"]), (q["x"], q["y"])), pl["player_id"])
                         for pl in rows[j]["players"] if pl["on_pitch"])
            add(r, "set_piece", team_of(pid), pid, b["x"], b["y"], kind=m)
        if p and touch and speed(r) >= th["shot_min_speed"]:
            t = touch[0]
            if (gx := kick_at(rows, i, touch, pt, last_shot, who, half, th["shot_min_speed"], th)) is not None:
                yg = b["y"] + b["vy"] * (gx - b["x"]) / b["vx"]
                if (abs(yg) <= th["shot_max_abs_y_m"] and r["game_state"] not in NOT_SHOT_STATES
                        and not teammate_next(raw, rows, i, t, touch[1], th["goal_lookahead"])):
                    k = next((k for k in range(i + 1, min(i + 1 + th["goal_lookahead"], len(rows)))
                              if rows[k]["score"][t] > r["score"][t]), None)
                    add(r, "shot", t, touch[1], b["x"], b["y"], end_x=round(gx, 2), end_y=round(yg, 2),
                        speed_m_s=round(speed(r), 2), outcome="no_goal" if k is None else "goal")
                    if k is not None:  # one goal, one "goal" shot: the last shot before the score change
                        if (t, k) in goal_shot:
                            goal_shot[t, k]["outcome"] = "no_goal"
                        goal_shot[t, k] = ev[-1]
        if not owners[i]:
            continue
        if last and owners[i] != last[:2]:
            (t1, p1, li), (t2, p2) = last, owners[i]
            carry(last, li)
            since = i
            if not any(is_break(rows[k - 1], rows[k]) for k in range(li + 1, i + 1)):
                o = rows[li]["ball"]
                end = dict(end_x=round(b["x"], 2), end_y=round(b["y"], 2))
                if t2 == t1:
                    add(r, "pass", t1, p1, o["x"], o["y"], to_player_id=p2, **end, outcome="complete", intercepted_by=None)
                elif i - li <= th["tackle_max_gap"] and math.dist(xy(rows[li], p1), xy(rows[li], p2)) < th["tackle_dist_m"]:
                    add(r, "tackle", t2, p2, b["x"], b["y"], from_player_id=p1)
                else:
                    add(r, "pass", t1, p1, o["x"], o["y"], to_player_id=None, **end, outcome="intercepted", intercepted_by=p2)
        elif last is None:
            since = i
        last = (*owners[i], i)
    if last:
        carry(last, last[2])
    ev.sort(key=lambda e: e["t_s"])
    return ev


def summarize(ev, frames, th):
    mins = frames * FRAME_S / 60
    s = dict(thresholds=th, frames=frames, in_play_engine_minutes=round(mins, 3),
             normalization_note="per minute of in-play engine time (frames*0.1 s); compare against real football "
                                "per minute of effective playing time, not per 90 minutes")
    for side in ("home", "away"):
        mine = [e for e in ev if e["team"] == side]
        pas = [e for e in mine if e["type"] == "pass"]
        done = sum(e["outcome"] == "complete" for e in pas)
        shots = sum(e["type"] == "shot" for e in mine)
        sp = {}
        for e in mine:
            if e["type"] == "set_piece":
                sp[e["kind"]] = sp.get(e["kind"], 0) + 1
        s[side] = dict(passes_attempted=len(pas), passes_completed=done,
                       pass_completion_pct=round(100 * done / len(pas), 1) if pas else None,
                       interceptions_suffered=sum(e["outcome"] == "intercepted" for e in pas),
                       tackles_won=sum(e["type"] == "tackle" for e in mine), shots=shots,
                       shots_on_target_line=shots, goals=sum(e["type"] == "goal" for e in mine), set_pieces=sp)
        s[side]["per_engine_minute"] = {k: round(v / mins, 2) for k, v in dict(
            passes_attempted=len(pas), passes_completed=done, interceptions_suffered=s[side]["interceptions_suffered"],
            tackles_won=s[side]["tackles_won"], shots=shots, goals=s[side]["goals"],
            set_pieces_total=sum(sp.values())).items()}
    s["both_teams_per_engine_minute"] = {k: round(s["home"]["per_engine_minute"][k] + s["away"]["per_engine_minute"][k], 2)
                                         for k in s["home"]["per_engine_minute"]}
    return s
