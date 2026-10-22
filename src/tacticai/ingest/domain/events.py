"""Pure event rules: infer football events from tracking rows (the engine exposes no events or actions)."""
import math

from .clock import FRAME_S
from .pitch import ENG_X as KX, ENG_Y as KY, speed_m_s

KINDS = {1: "kick_off", 2: "goal_kick", 3: "free_kick", 4: "corner", 5: "throw_in", 6: "penalty"}
SIDE = {0: "left", 1: "right", None: None}
DEFAULTS = dict(tackle_dist_m=2.0, tackle_max_gap=2, shot_min_speed=15.0, shot_goal_margin_m=2.0,
                shot_max_dist_m=35.0, shot_debounce=10, goal_lookahead=30)


def speed(r):
    return speed_m_s(r["ball_direction"][0], r["ball_direction"][1])


def r2(p):
    return None if p is None else [round(p[0], 2), round(p[1], 2)]


def is_pass(rows, s, t):
    """True if the first owner after row s is team t (no decision -> False)."""
    for k in range(s + 1, len(rows)):
        a, b = rows[k - 1], rows[k]
        if (a["game_mode"] == 0 and b["game_mode"] != 0) or a["score"] != b["score"]:
            return False
        if b["ball_owned_team"] != -1:
            return b["ball_owned_team"] == t
    return False


def extract(rows, th):
    ev = []

    def add(r, typ, team, player, origin, dest, **kw):
        ev.append(dict(step=r["step"], frame_index=r["frame_index"], match_time_s=r["match_time_s"],
                       engine_time_s=r["engine_time_s"], type=typ, team=team, team_side=SIDE[team],
                       player=player, **kw, origin_eng=r2(origin), dest_eng=r2(dest)))

    last = None  # (team, player, row index of last owned step)
    last_shot = {0: -10**9, 1: -10**9}
    for i, r in enumerate(rows):
        p = rows[i - 1] if i else None
        if p and r["score"] != p["score"]:
            t = 0 if r["score"][0] > p["score"][0] else 1
            add(r, "goal", t, last[1] if last and last[0] == t else None, r["ball_eng"][:2], None,
                last_owner_team=last[0] if last else None)
        if p and r["game_mode"] != p["game_mode"] and r["game_mode"] in KINDS:
            m, j = r["game_mode"], i
            while j + 1 < len(rows) and rows[j + 1]["game_mode"] == m:
                j += 1
            q, bx = rows[j], rows[j]["ball_eng"][:2]
            d, t, pl = min((math.dist(xy, bx), tm, k) for tm, key in ((0, "left_team_eng"), (1, "right_team_eng"))
                           for k, xy in enumerate(q[key]))
            add(r, "set_piece", t, pl, r["ball_eng"][:2], None, kind=KINDS[m], taker_dist_m=round(d, 2))
        if p and last and speed(r) >= th["shot_min_speed"] > speed(p):
            t, (x, y, _), (dx, dy, _) = last[0], r["ball"], r["ball_direction"]
            gx = 1 if t == 0 else -1
            if dx * gx > 0 and i - last_shot[t] > th["shot_debounce"]:
                yg = y + dy * (gx - x) / dx
                if (abs(yg * KY) <= 3.68 + th["shot_goal_margin_m"] and abs(gx - x) * KX <= th["shot_max_dist_m"]
                        and not is_pass(rows, i, t)):
                    last_shot[t] = i
                    goal = any(q["score"][t] > r["score"][t] for q in rows[i + 1:i + 1 + th["goal_lookahead"]])
                    add(r, "shot", t, last[1], r["ball_eng"][:2], [gx * KX, yg * KY],
                        speed_m_s=round(speed(r), 2), outcome="goal" if goal else "no_goal")
        t2, p2 = r["ball_owned_team"], r["ball_owned_player"]
        if t2 == -1:
            continue
        if last and (t2, p2) != last[:2]:
            t1, p1, li = last
            brk = any((rows[k - 1]["game_mode"] == 0 and rows[k]["game_mode"] != 0)
                      or rows[k]["score"] != rows[k - 1]["score"] for k in range(li + 1, i + 1))
            if not brk:
                lr = rows[li]
                o, d = lr["ball_eng"][:2], r["ball_eng"][:2]
                if t2 == t1:
                    add(r, "pass", t1, p1, o, d, from_player=p1, to_player=p2, outcome="complete")
                else:
                    a = lr["left_team_eng" if t1 == 0 else "right_team_eng"][p1]
                    b = lr["left_team_eng" if t2 == 0 else "right_team_eng"][p2]
                    if i - li <= th["tackle_max_gap"] and math.dist(a, b) < th["tackle_dist_m"]:
                        add(r, "tackle", t2, p2, o, d, from_player=p1)
                    else:
                        add(r, "pass", t1, p1, o, d, from_player=p1, outcome="intercepted",
                            intercepted_by=dict(team=t2, player=p2))
        last = (t2, p2, i)
    ev.sort(key=lambda e: e["step"])
    return ev


def summarize(ev, steps, th):
    mins = steps * FRAME_S / 60
    s = dict(thresholds=th, steps=steps, in_play_engine_minutes=round(mins, 3),
             normalization_note="per minute of in-play engine time (steps*0.1 s); compare against real football "
                                "per minute of effective playing time, not per 90'",
             set_pieces_unattributed=sum(e["type"] == "set_piece" and e["team"] is None for e in ev))
    for t, side in ((0, "left"), (1, "right")):
        mine = [e for e in ev if e["team"] == t]
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
    s["both_teams_per_engine_minute"] = {k: round(s["left"]["per_engine_minute"][k] + s["right"]["per_engine_minute"][k], 2)
                                         for k in s["left"]["per_engine_minute"]}
    return s
