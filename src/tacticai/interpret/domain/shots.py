"""Pure kick-candidate features: every ball strike toward goal, with tracking features and tracking-only outcome labels.
Owners follow the ingest rules (infer_owner raw touch, stable_owners for is_pass); the labels never read ingest events."""
import math

from ...ingest.domain.events import POST_M, infer_owner, is_pass, speed, stable_owners

MIN_SPEED, JUMP_M_S, MAX_DIST_M, DEBOUNCE, LOOKAHEAD_S, HALF_G = 10.0, 5.0, 40.0, 10, 3.0, 4.905
BOX_DEPTH_M, BOX_HALF_W_M, CROSSBAR_M = 16.5, 20.16, 2.44


def visible_angle_deg(x, y, gx):
    """Angle subtended by the two posts seen from (x, y), degrees."""
    ax, ay, bx, by = gx - x, -POST_M - y, gx - x, POST_M - y
    return math.degrees(math.atan2(abs(ax * by - ay * bx), ax * bx + ay * by))


def in_triangle(p, a, b, c):
    """p strictly inside triangle abc."""
    s = [(q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]) for q, r in ((a, b), (b, c), (c, a))]
    return all(v > 0 for v in s) or all(v < 0 for v in s)


def dist_to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = 0 if dx == dy == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def outcome_of(rows, raw, i, team, shooter, dist_line, pitch):
    """Tracking-only labels for the kick at row i, looking LOOKAHEAD_S ahead -> (outcome, next owner (team, player_id, role) or None, goal_in_sequence).
    The shooter's own continued contact is not a new owner. goal: the team scores before any touch by a teammate of the shooter (opponent
    touches do not cancel it); goal_in_sequence: it scores in the window whoever touches. Chronological: the ball beyond a line of
    pitch (half length, half width) or a frame_index gap (stoppage; in-play-only tracking) before any other touch is "out"."""
    r0, (hx, hy) = rows[i], pitch
    goal = seq = mate = False
    out = own = None
    for k in range(i + 1, len(rows)):
        r = rows[k]
        if r["t_s"] > r0["t_s"] + LOOKAHEAD_S:
            break
        if not seq and r["score"][team] > r0["score"][team]:
            seq, goal = True, not mate
        if out is None and own is None and (abs(r["ball"]["x"]) > hx or abs(r["ball"]["y"]) > hy or r["frame_index"] - rows[k - 1]["frame_index"] > 1):
            out = k
        if raw[k] and raw[k][1] != shooter:
            own, mate = own or k, mate or raw[k][0] == team
    nxt = None
    if own is not None:
        role = next(p["role"] for p in rows[own]["players"] if p["player_id"] == raw[own][1])
        nxt = (*raw[own], role)
    if goal:
        return "goal", nxt, seq
    if out is not None:
        return "out", nxt, seq
    if nxt is None:
        return "other", nxt, seq
    if nxt[0] == team:
        return "kept", nxt, seq
    if nxt[2] == "GK":
        return "saved", nxt, seq
    b0, b1 = r0["ball"], rows[own]["ball"]
    return ("blocked" if math.dist((b0["x"], b0["y"]), (b1["x"], b1["y"])) < 0.5 * dist_line else "other"), nxt, seq


def kick_candidates(rows, roster, meta, th, events=None):
    """Every strike toward the opponent goal (see module doc) -> list of flat dicts; events (ingest) only feeds detected_as_shot_by_ingest."""
    half, pitch = meta["pitch"]["length_m"] / 2, (meta["pitch"]["length_m"] / 2, meta["pitch"]["width_m"] / 2)
    info = {p["player_id"]: p for p in roster["players"]}
    raw = [infer_owner(r, th["owner_radius_m"], th["owner_max_z_m"]) for r in rows]
    owners = stable_owners(raw, th["owner_min_frames"])
    shots = [(e["team"], e["frame_index"]) for e in events or [] if e["type"] == "shot"]
    last, who, touch, change_t, res = {"home": -10**9, "away": -10**9}, {}, None, rows[0]["t_s"] if rows else 0, []
    for i, r in enumerate(rows):
        if i and rows[i - 1]["game_state"] != r["game_state"]:
            change_t = r["t_s"]
        prev = touch
        if i and raw[i - 1]:
            touch = raw[i - 1]
        if not (i and touch and speed(r) >= MIN_SPEED):
            continue
        v0, team = speed(rows[i - 1]), touch[0]
        if not (v0 < MIN_SPEED or speed(r) - v0 >= JUMP_M_S or touch != prev and touch[1] != who.get(team)):
            continue
        b = r["ball"]
        gx = half if team == "home" else -half
        if b["vx"] * gx <= 0 or abs(gx - b["x"]) > MAX_DIST_M or i - last[team] < DEBOUNCE and touch[1] == who.get(team):
            continue
        last[team], who[team] = i, touch[1]
        x, y, z, opp = b["x"], b["y"], b["z"], "away" if team == "home" else "home"
        dline, t = abs(gx - x), (gx - x) / b["vx"]
        py, pz = y + b["vy"] * t, z + b["vz"] * t - HALF_G * t * t
        posts = ((gx, -POST_M), (gx, POST_M))
        mates = [p for p in r["players"] if p["on_pitch"] and p["player_id"].startswith(team)]
        opps = [p for p in r["players"] if p["on_pitch"] and p["player_id"].startswith(opp)]
        gk = next((p for p in opps if p["role"] == "GK"), None)
        tgt = (gx, max(-POST_M, min(POST_M, py)))
        dd = [math.dist((p["x"], p["y"]), (x, y)) for p in opps]
        outcome, nxt, seq = outcome_of(rows, raw, i, team, touch[1], dline, pitch)
        res.append(dict(
            match_id=meta["match_id"], frame_index=r["frame_index"], t_s=r["t_s"], clock_s=r["clock_s"], period=r["period"],
            team=team, shooter_id=touch[1], shooter_role=info[touch[1]]["role"], shooter_number=info[touch[1]]["number"],
            ball_x=round(x, 2), ball_y=round(y, 2), ball_z=round(z, 2), ball_vx=round(b["vx"], 2), ball_vy=round(b["vy"], 2),
            ball_vz=round(b["vz"], 2), speed_m_s=round(speed(r), 2),
            dist_goal_center_m=round(math.dist((x, y), (gx, 0)), 2), dist_goal_line_m=round(dline, 2),
            angle_to_goal_center_deg=round(math.degrees(math.atan2(abs(y), dline)), 1),
            visible_goal_angle_deg=round(visible_angle_deg(x, y, gx), 1),
            projected_y_at_goal_m=round(py, 2), projected_z_at_goal_m=round(pz, 2),
            on_target_projection=abs(py) <= POST_M and 0 <= pz <= CROSSBAR_M,
            in_box=dline <= BOX_DEPTH_M and abs(y) <= BOX_HALF_W_M, header=z > 1.0,
            nearest_defender_m=round(min(dd), 2) if dd else None, defenders_within_3m=sum(d <= 3 for d in dd),
            defenders_in_cone=sum(p["role"] != "GK" and in_triangle((p["x"], p["y"]), (x, y), *posts) for p in opps),
            gk_present=gk is not None,
            gk_dist_to_goal_line_m=gk and round(abs(gx - gk["x"]), 2),
            gk_dist_to_shot_line_m=gk and round(dist_to_segment((gk["x"], gk["y"]), (x, y), tgt), 2),
            gk_off_line_m=gk and round(math.dist((gk["x"], gk["y"]), (gx, 0)), 2),
            score_diff=r["score"][team] - r["score"][opp], game_state=r["game_state"],
            previous_game_state_change_s=round(r["t_s"] - change_t, 1),
            is_pass_by_ingest_rule=is_pass(rows, owners, i, team),
            detected_as_shot_by_ingest=None if events is None else any(
                t == team and abs(f - r["frame_index"]) <= 3 for t, f in shots),
            teammates=[[round(p["x"], 2), round(p["y"], 2), p["role"]] for p in mates],
            opponents=[[round(p["x"], 2), round(p["y"], 2), p["role"]] for p in opps],
            goal=outcome == "goal", goal_in_sequence=seq, next_owner_team=nxt and nxt[0], next_owner_role=nxt and nxt[2], outcome=outcome))
    return res
