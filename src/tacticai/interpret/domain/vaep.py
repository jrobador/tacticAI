"""Light VAEP (Decroos et al.): actions from events_enriched, game-state features, scores/concedes labels, per-action value and the per-player rating.
Pure functions. A model is a callable f(feature_dict) -> (P_scores, P_concedes) for the team of the action (see interpret.application.models.load_vaep)."""
import math

from .frame import opponent

LENGTH_M, POST_Y = 108.8, 3.66
HORIZON = 10  # labels look at actions i..i+HORIZON
TYPES = ("pass", "interception", "tackle", "shot")
UNIT, SCOPE = "goals_added", "full_match"

_SLOT = list(TYPES) + ["success", "xa", "ya", "end_xa", "end_ya", "dist", "angle", "end_dist", "end_angle", "dx", "same_team"]
FEATURES = [f"a{k}_{n}" for k in range(3) for n in _SLOT] + ["seconds", "score_diff", "xg"]  # a0 = a_i, a1 = a_{i-1}, a2 = a_{i-2}
BASELINE = ["a0_xa", "a0_ya"]


def build_actions(events):
    """events_enriched rows, in order -> actions. Each action: type, team, player_id, t_s, period, x, y, end_x, end_y (metres, absolute), success,
    xg, score_before, event_index, reset (a goal, set piece or period change came between the previous action and this one) and goals_after
    (teams that scored after this action and before the next one, same period)."""
    acts, reset = [], True
    for j, e in enumerate(events):
        t = e["type"]
        if t in ("goal", "set_piece"):
            if t == "goal" and acts and acts[-1]["period"] == e["period"]:
                acts[-1]["goals_after"].append(e["team"])
            reset = True
            continue
        if t not in ("pass", "tackle", "shot"):
            continue
        if acts and acts[-1]["period"] != e["period"]:
            reset = True
        base = dict(t_s=e["t_s"], period=e["period"], xg=0.0, score_before=e["score_before"], event_index=j)
        if t == "pass":
            made = [dict(type="pass", team=e["team"], player_id=e["player_id"], x=e["x"], y=e["y"], end_x=e["end_x"], end_y=e["end_y"], success=e["outcome"] == "complete")]
            if e.get("intercepted_by"):  # credited to the interceptor's team at the pass end point
                made.append(dict(type="interception", team=opponent(e["team"]), player_id=e["intercepted_by"], x=e["end_x"], y=e["end_y"], end_x=e["end_x"], end_y=e["end_y"], success=True))
        elif t == "tackle":
            made = [dict(type="tackle", team=e["team"], player_id=e["player_id"], x=e["x"], y=e["y"], end_x=e["x"], end_y=e["y"], success=True)]
        else:
            made = [dict(type="shot", team=e["team"], player_id=e["player_id"], x=e["x"], y=e["y"], end_x=e["end_x"], end_y=e["end_y"], success=e["outcome"] == "goal", xg=e.get("xg") or 0.0)]
        for a in made:
            acts.append({**base, **a, "reset": reset, "goals_after": []})  # fresh list per action
            reset = False
    return acts


def labels(actions):
    """-> [(scores, concedes)] per action: a goal by the team of a_i / the rival after any action in i..i+HORIZON, never crossing a period or the end of the list."""
    out = []
    for i, a in enumerate(actions):
        end = i
        while end < min(i + HORIZON, len(actions) - 1) and actions[end + 1]["period"] == a["period"]:
            end += 1
        goals = [g for b in actions[i:end + 1] for g in b["goals_after"]]
        out.append((a["team"] in goals, opponent(a["team"]) in goals))
    return out


def _angle(xa, ya, half_l):
    """Angle subtended by the two posts, radians."""
    ax, ay, bx, by = half_l - xa, POST_Y - ya, half_l - xa, -POST_Y - ya
    return abs(math.atan2(ax * by - ay * bx, ax * bx + ay * by))


def features(actions, i, length_m=LENGTH_M):
    """-> {name: float} for the state a_{i-2}, a_{i-1}, a_i, coordinates relative to the team of a_i (home attacks +x). Missing earlier actions repeat the earliest one of the period."""
    a, half_l = actions[i], length_m / 2
    s = 1 if a["team"] == "home" else -1
    idx = [i]
    for _ in range(2):
        j = idx[-1] - 1
        idx.append(j if j >= 0 and actions[j]["period"] == a["period"] else idx[-1])
    f = {}
    for k, j in enumerate(idx):
        b = actions[j]
        xa, ya, exa, eya = s * b["x"], s * b["y"], s * b["end_x"], s * b["end_y"]
        f.update({f"a{k}_{t}": float(b["type"] == t) for t in TYPES})
        f.update({f"a{k}_success": float(b["success"]), f"a{k}_xa": xa, f"a{k}_ya": ya, f"a{k}_end_xa": exa, f"a{k}_end_ya": eya,
                  f"a{k}_dist": math.hypot(half_l - xa, ya), f"a{k}_angle": _angle(xa, ya, half_l),
                  f"a{k}_end_dist": math.hypot(half_l - exa, eya), f"a{k}_end_angle": _angle(exa, eya, half_l),
                  f"a{k}_dx": exa - xa, f"a{k}_same_team": float(b["team"] == a["team"])})
    sb = a["score_before"]
    f.update(seconds=a["t_s"] - actions[idx[2]]["t_s"], score_diff=float(sb[a["team"]] - sb[opponent(a["team"])]), xg=float(a["xg"]) if a["type"] == "shot" else 0.0)
    return f


def dataset_rows(actions, length_m=LENGTH_M):
    """One training row per action: type, the features and the labels scores / concedes (0 or 1)."""
    return [{"type": a["type"], **features(actions, i, length_m), "scores": int(sc), "concedes": int(co)} for i, (a, (sc, co)) in enumerate(zip(actions, labels(actions)))]


def action_values(actions, model, length_m=LENGTH_M):
    """-> [{offensive, defensive, total}] per action (unrounded). The previous state is flipped when a_{i-1} is the other team and is 0 after a reset."""
    probs = [model(features(actions, i, length_m)) for i in range(len(actions))]
    out = []
    for i, a in enumerate(actions):
        ps, pc = probs[i]
        p0s, p0c = (0.0, 0.0) if a["reset"] else probs[i - 1] if actions[i - 1]["team"] == a["team"] else probs[i - 1][::-1]
        off, de = ps - p0s, -(pc - p0c)
        out.append({"offensive": off, "defensive": de, "total": off + de})
    return out


def vaep_rating(player_id, role, actions, values):
    """Rating dict of players.json: sum of the player's action values in goals added, with a breakdown by action type (items summing 0 are omitted).
    GK -> null (saves_not_validated); values None (no model) -> null (vaep_model_missing)."""
    r = {"value": None, "unit": UNIT, "scope": SCOPE, "breakdown": [], "reason": None}
    if role == "GK":
        return {**r, "reason": "saves_not_validated"}
    if values is None:
        return {**r, "reason": "vaep_model_missing"}
    agg = {}
    for a, v in zip(actions, values):
        if a["player_id"] == player_id:
            c = agg.setdefault(a["type"], [0, 0.0, 0.0])
            c[0], c[1], c[2] = c[0] + 1, c[1] + v["offensive"], c[2] + v["defensive"]
    bd = []
    for t in TYPES:
        if t in agg and agg[t][1] + agg[t][2]:
            n, o, d = agg[t]
            o, d = round(o, 3), round(d, 3)
            bd.append({"item": t, "count": n, "offensive": o, "defensive": d, "points": round(o + d, 3)})
    return {**r, "value": round(sum(b["points"] for b in bd), 3), "breakdown": bd}
