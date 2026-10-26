"""Director: rules plan, agent-plan validation and /overlays assembly. Deterministic, no I/O except the brand files.
API:
    priority(insight, club, player=None) -> float
    rules_plan(insights, lens, club, metric=None) -> [{"insight_id", "slot", "duration_s", "reason"}] sorted by show_t_s
    validate_plan(plan, insights, lens) -> list[str]            # [] = valid
    assemble_overlays(...) -> the exact /overlays JSON"""
import json
from pathlib import Path

from ...explain.domain import placeholders as P
from ...personalize.domain.lenses import CLUB_BONUS, LENSES, PLAYER_BONUS

THRESHOLD = {k: v["threshold"] for k, v in LENSES.items()}
SLOTS = {k: list(v["slots"]) for k, v in LENSES.items()}

PREFERRED = {"lines_broken": "bottom_left", "goal_or_chance": "bottom_left", "pressure_spell": "top_right", "momentum_shift": "top_right"}
MIN_DURATION, MAX_DURATION = 4, 10
METRIC_KINDS = {"pressure": ["pressure_spell"], "xg": ["goal_or_chance"], "possession": [], "goals_added": ["lines_broken", "goal_or_chance"]}
METRIC_UNIT = {"pressure": "0-1", "xg": "engine xG", "possession": "%", "goals_added": "goals_added"}
BRANDS = ("tacticai", "bka-tv")
BRANDS_DIR = Path(__file__).resolve().parents[1] / "brands"


def duration(ins):
    return 8 if ins["kind"] == "goal_or_chance" and ins["subtype"] == "goal" else 6


def priority(ins, club="neutral", player=None):
    bonus = (CLUB_BONUS if club in ("home", "away") and ins["team"] == club else 0) + (PLAYER_BONUS if player and player in ins["players"] else 0)
    return round(min(1.0, max(0.0, ins["importance"]["value"] + bonus)), 3)


def main_metric(ins):
    k, s = ins["kind"], ins["subtype"]
    name = {"lines_broken": "lines_broken", "goal_or_chance": "xg"}.get(k)
    if k == "pressure_spell":
        name = "value" if s == "peak" else "after"
    elif k == "momentum_shift":
        name = "after" if s == "swing" else "mean_momentum"
    return name if name in ins["metrics"] else None


def _slot_order(kind, lens):
    slots = SLOTS[lens]
    pref = PREFERRED[kind]
    return ([pref] if pref in slots else []) + [s for s in slots if s != pref]


def _overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


def rules_plan(insights, lens, club, metric=None):
    """Spec 'Plan por reglas'. For one_metric pass `metric` (restricts the kinds). Priority includes the club bonus, never the player bonus."""
    kinds = METRIC_KINDS[metric] if lens == "one_metric" else None
    cands = [(priority(i, club), i) for i in insights if priority(i, club) >= THRESHOLD[lens] and (kinds is None or i["kind"] in kinds)]
    cands.sort(key=lambda c: (-c[0], c[1]["show_t_s"], c[1]["insight_id"]))
    out, taken = [], {s: [] for s in SLOTS[lens]}
    for pr, i in cands:
        d = duration(i)
        if lens == "broadcast":
            out.append((i, None, d, pr))
            continue
        iv = (i["show_t_s"], i["show_t_s"] + d)
        for s in _slot_order(i["kind"], lens):
            if not any(_overlaps(iv, t) for t in taken[s]):
                taken[s].append(iv)
                out.append((i, s, d, pr))
                break
    out.sort(key=lambda o: (o[0]["show_t_s"], o[0]["insight_id"]))
    return [{"insight_id": i["insight_id"], "slot": s, "duration_s": d, "reason": f"rules: priority {pr} >= {THRESHOLD[lens]}"} for i, s, d, pr in out]


def validate_plan(plan, insights, lens):
    if not isinstance(plan, list):
        return ["plan must be a list"]
    ids = {i["insight_id"] for i in insights}
    errors, seen, taken = [], set(), {}
    by_id = {i["insight_id"]: i for i in insights}
    for k, o in enumerate(plan):
        if not isinstance(o, dict):
            errors.append(f"overlay {k}: not an object")
            continue
        iid, slot, d = o.get("insight_id"), o.get("slot"), o.get("duration_s")
        if iid not in ids:
            errors.append(f"overlay {k}: unknown insight_id {iid!r}")
            continue
        if iid in seen:
            errors.append(f"overlay {k}: duplicate insight_id {iid}")
        seen.add(iid)
        if lens == "broadcast":
            if slot is not None:
                errors.append(f"{iid}: broadcast has no slots")
        elif slot not in SLOTS[lens]:
            errors.append(f"{iid}: slot {slot!r} not in {SLOTS[lens]}")
        if isinstance(d, bool) or not isinstance(d, (int, float)) or not MIN_DURATION <= d <= MAX_DURATION:
            errors.append(f"{iid}: duration_s {d!r} outside {MIN_DURATION}..{MAX_DURATION}")
            continue
        if slot in SLOTS[lens]:
            iv = (by_id[iid]["show_t_s"], by_id[iid]["show_t_s"] + d)
            if any(_overlaps(iv, t) for t in taken.get(slot, [])):
                errors.append(f"{iid}: overlaps another overlay in {slot}")
            taken.setdefault(slot, []).append(iv)
    return errors


def _step_series(events, has_vaep):
    if not has_vaep:
        return False, "vaep_model_missing", []
    pts, h, a = [{"t_s": 0.0, "home": 0.0, "away": 0.0}], 0.0, 0.0
    for e in events:
        gains = {e["team"]: (e.get("vaep") or {}).get("total", 0.0), ("away" if e["team"] == "home" else "home"): (e.get("vaep_interception") or {}).get("total", 0.0)}
        if e.get("vaep") or e.get("vaep_interception"):
            h, a = h + gains["home"], a + gains["away"]
            pts.append({"t_s": e["t_s"], "home": round(h, 3), "away": round(a, 3)})
    return True, None, pts


def metric_series(metric, timeline, events, has_vaep=True):
    base = {"metric": metric, "unit": METRIC_UNIT[metric], "mode": "steps" if metric == "goals_added" else "windows"}
    if metric == "goals_added":
        ok, reason, pts = _step_series(events or [], has_vaep)
        return {**base, "available": ok, "reason": reason, "points": pts}
    if timeline is None:
        return {**base, "available": False, "reason": "timeline_missing", "points": []}
    key = {"pressure": "pressure", "xg": "xg", "possession": "possession_share"}[metric]

    def val(w, t):
        v = w[t][key]
        return None if v is None else round(v * 100, 1) if metric == "possession" else round(v, 3)
    return {**base, "available": True, "reason": None,
            "points": [{"from_t_s": w["start_t_s"], "until_t_s": w["end_t_s"], "home": val(w, "home"), "away": val(w, "away")} for w in timeline]}


def _player_focus(chosen, insights, lens, club, player, kinds):
    """chosen: list of dicts {ins, slot, duration_s, priority, director}. Adds the player's missing insights (rules) and returns the new list."""
    thr = THRESHOLD[lens]
    have = {c["ins"]["insight_id"] for c in chosen}
    cands = [(priority(i, club, player), i) for i in insights
             if player in i["players"] and i["insight_id"] not in have and priority(i, club, player) >= thr and (kinds is None or i["kind"] in kinds)]
    cands.sort(key=lambda c: (-c[0], c[1]["show_t_s"], c[1]["insight_id"]))
    for pr, i in cands:
        d = duration(i)
        if lens == "broadcast":
            chosen.append({"ins": i, "slot": None, "duration_s": d, "priority": pr, "director": "rules"})
            continue
        iv = (i["show_t_s"], i["show_t_s"] + d)
        free, swap = None, None
        for s in _slot_order(i["kind"], lens):
            hit = [c for c in chosen if c["slot"] == s and _overlaps(iv, (c["ins"]["show_t_s"], c["ins"]["show_t_s"] + c["duration_s"]))]
            if not hit and free is None:
                free = (s, [])
            elif hit and swap is None and all(player not in c["ins"]["players"] and c["priority"] < pr for c in hit):
                swap = (s, hit)
        pick = free or swap
        if pick:
            chosen = [c for c in chosen if not any(c is h for h in pick[1])]
            chosen.append({"ins": i, "slot": pick[0], "duration_s": d, "priority": pr, "director": "rules"})
    return chosen


def assemble_overlays(insights, plans, variants, lens, lang, club, player, metric, brand, roster, players_json, timeline, events, has_vaep=True):
    """insights: list from explain/insights.jsonl (None = not enriched). plans: {"<lens>_<club>": plan json}. variants: {"<lens>_<lang>_<club>": variant json}.
    roster: {player_id: {...}}. players_json: interpret/players.json (dict with "players") or None. timeline: list of rows or None. events: events_enriched rows or None.
    has_vaep: the VAEP model exists (interpret/meta.json models.vaep). -> /overlays dict. ValueError on a bad parameter (the API validates first and answers 422)."""
    if lens not in THRESHOLD or lang not in ("en", "es") or club not in ("neutral", "home", "away") or brand not in BRANDS:
        raise ValueError("bad lens, lang, club or brand")
    if (metric is not None and lens != "one_metric") or (metric is not None and metric not in METRIC_KINDS):
        raise ValueError("bad metric")
    if player is not None and player not in roster:
        raise ValueError("player not in roster")
    metric = (metric or "pressure") if lens == "one_metric" else None
    text_lens = "analyst" if lens in ("broadcast", "one_metric") else lens
    variant = (variants or {}).get(f"{text_lens}_{lang}_{club}")
    plan = None if lens == "one_metric" else (plans or {}).get(f"{lens}_{club}")
    if insights is None or variant is None or (lens != "one_metric" and plan is None):
        return {"available": False, "reason": "not_enriched"}
    by_id = {i["insight_id"]: i for i in insights}
    if lens == "one_metric":
        director, entries = "rules", rules_plan(insights, lens, club, metric)
    else:
        director, entries = plan["source"], plan["overlays"]
    kinds = METRIC_KINDS[metric] if lens == "one_metric" else None
    chosen = [{"ins": by_id[e["insight_id"]], "slot": e["slot"], "duration_s": e["duration_s"], "priority": priority(by_id[e["insight_id"]], club, player), "director": director}
              for e in entries]
    if player:
        chosen = _player_focus(chosen, insights, lens, club, player, kinds)
    chosen.sort(key=lambda c: (c["ins"]["show_t_s"], c["ins"]["insight_id"]))
    overlays = []
    for k, c in enumerate(chosen):
        i = c["ins"]
        t = variant["texts"].get(i["insight_id"])
        title, text, lsrc = (t["title"], t["text"], t["source"]) if t else (i["text"]["fact"], i["text"]["why"], "template")
        main = main_metric(i)
        shown = i["metrics"] if lens in ("analyst", "broadcast") else {main: i["metrics"][main]} if main else {}
        overlays.append({"overlay_id": f"o{k}", "insight_id": i["insight_id"], "show_t_s": i["show_t_s"], "duration_s": c["duration_s"], "slot": c["slot"],
                         "priority": c["priority"], "title": P.resolve_text(title, i["metrics"], lang=lang), "text": P.resolve_text(text, i["metrics"], lang=lang), "metrics": shown,
                         "trail": {"explainer": i["text"]["source"], "lens": lsrc, "director": c["director"]}})
    card = None
    if player:
        rating = next((p.get("rating") for p in (players_json or {}).get("players", []) if p["player_id"] == player), None)
        card = {"player_id": player, "rating": rating, "insight_ids": [i["insight_id"] for i in insights if player in i["players"]]}
    tokens = json.loads((BRANDS_DIR / f"{brand}.json").read_text(encoding="utf-8")) if lens == "broadcast" else None
    return {"overlays_version": 1, "available": True, "lens": lens, "lang": lang, "club": club, "player": player, "metric": metric, "brand": brand,
            "director": director, "overlays": overlays, "metric_series": metric_series(metric, timeline, events, has_vaep) if metric else None,
            "player_card": card, "brand_tokens": tokens}
