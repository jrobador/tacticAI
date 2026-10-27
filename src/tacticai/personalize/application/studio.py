"""personalize/studio/<lang>.json: the full-time studio script for the presenter (Studio Script Agent), one per language.
Built from personalize/fan/facts.json without a side. Every line passes the pipeline's contract (placeholders, claims, names) and the
Fan judge in the presenter's voice; a rejected script goes back once with the reasons, then falls back to a line of data per goal and shot."""
import json
import os

from ...agents import fan_judge
from ...core.files import read_json, write_atomic
from ..domain import fan_locale as L
from ..domain.lenses import LANGS
from . import fan, studio_agent

STUDIO_VERSION = 1
#: The plays the script may pick from: what a full-time show replays.
REPLAYABLE = ("goal", "save", "miss", "mistake", "tackle", "pass", "carry", "move")


def brief(facts, ctx, lang):
    plays = []
    for f in facts["facts"]:
        if f["kind"] not in REPLAYABLE:
            continue
        people = [{"name": ctx.players[p["player_id"]], "role": p["role"]} for p in fan.V.player_roles(f, ctx.team_of)]
        plays.append({"fact_id": f["fact_id"], "kind": f["kind"], "team": ctx.teams[f["team"]], "people": people,
                      **({"shot_from": L.SHOT_FROM[lang][f["where"]]} if f.get("where") else {}),
                      **{k: f[k] for k in fan.FACT_DETAILS if f.get(k) is not None}, "claims": f["claims"],
                      "placeholders": [f"{{{k}}}" for k in f["metrics"] if k != "minute"] + ["{home_short}", "{away_short}"]})
    v = facts["verdict"]
    return {"teams": {s: {"name": ctx.teams[s], "short": ctx.meta["teams"][s]["short"]} for s in ("home", "away")},
            "result": {"winner": ctx.teams.get(v["winner"]), "deserved": v["deserved"], "star": ctx.players.get(v["figure"]) if v["figure"] else None,
                       "placeholders": ["{home_goals}", "{away_goals}", "{home_short}", "{away_short}"]},
            "awards": [{"award": L.AWARD[lang][a["award"]][0], "name": ctx.players[a["player_id"]]} for a in facts.get("awards", [])],
            "plays": plays}


def _fallback(facts, ctx, lang):
    v = facts["verdict"]
    head, text = L.verdict(fan.V.result(v["winner"], "neutral"), ctx.teams.get(v["winner"]), ctx.players.get(v["figure"]) if v["figure"] else None, lang)
    segs = []
    for f in facts["facts"]:
        if f["kind"] in ("goal", "save", "miss"):
            names = [ctx.players[p["player_id"]] for p in fan.V.player_roles(f, ctx.team_of)]
            segs.append((f, " · ".join(L.moment(f, names, lang))))
    return f"{head}. {text}", segs, ""


def _contract(facts, ctx, got, lang):
    """-> {part: reason}: the pipeline's contract on every line (placeholders, claims, names) and segments that are replayable plays."""
    v, by_id = facts["verdict"], {f["fact_id"]: f for f in facts["facts"]}
    vm = {k: v["metrics"][k] for k in ("home_goals", "away_goals")}
    star = ctx.players.get(v["figure"]) if v["figure"] else None
    bad = {}
    segs = got.get("segments") or []
    if not 1 <= len(segs) <= 6 or any(by_id.get(x.get("fact_id"), {}).get("kind") not in REPLAYABLE for x in segs):
        bad["segments"] = "segments must be 1 to 6 replayable plays of the match"
    for x in segs:
        f = by_id.get(x.get("fact_id"))
        if f:
            names = [ctx.players[p["player_id"]] for p in fan.V.player_roles(f, ctx.team_of)]
            e = fan.check(x.get("text"), f["metrics"], f["claims"], lang, names + list(ctx.teams.values()), ctx.every, ctx.meta)
            if e:
                bad[f["fact_id"]] = "; ".join(e)
    allowed = list(ctx.teams.values()) + ([star] if star else []) + [ctx.players[a["player_id"]] for a in facts.get("awards", [])]
    goal_claims = sorted({c for f in facts["facts"] if f["kind"] == "goal" for c in f["claims"]})  # the opening may say what the goals were
    for part in ("opening", "closing"):
        e = fan.check(got.get(part), vm, goal_claims, lang, allowed, ctx.every, ctx.meta)
        if e:
            bad[part] = "; ".join(e)
    return bad


def _review(facts, ctx, got, lang, b, judge):
    """-> {part: reason} of a script: the contract on every part, then the Fan judge, in the presenter's voice, on the parts that passed it."""
    bad = _contract(facts, ctx, got, lang)
    if "segments" in bad:
        return bad
    briefs = {p["fact_id"]: p for p in b["plays"]}
    items = [{"id": "opening", "text": got["opening"], "brief": b["result"]}, {"id": "closing", "text": got["closing"], "brief": {**b["result"], "awards": b["awards"]}}]
    items += [{"id": x["fact_id"], "text": x["text"], "brief": briefs[x["fact_id"]]} for x in got["segments"]]
    return {**bad, **judge([i for i in items if i["id"] not in bad], {"language": b["language"], "reader": "viewers of a neutral studio show"}, voice="presenter")}


def script(facts, ctx, got, lang, bad=()):
    """The studio script of one language. Like the fan view, a rejected part is replaced alone: a rejected opening by the result line,
    a rejected segment is dropped (the data lines of the goals and shots when none is left), a rejected closing is left out."""
    v, by_id = facts["verdict"], {f["fact_id"]: f for f in facts["facts"]}
    vm = {k: v["metrics"][k] for k in ("home_goals", "away_goals")}
    fb_open, fb_segs, _ = _fallback(facts, ctx, lang)
    got = got or {}
    opening = got["opening"] if got and "opening" not in bad else fb_open
    closing = got["closing"] if got and "closing" not in bad else ""
    segs = [(by_id[x["fact_id"]], x["text"]) for x in got.get("segments") or [] if "segments" not in bad and x["fact_id"] not in bad]
    segs = segs or fb_segs
    kept = bool(got) and not bad
    source = "agent" if kept else "fallback" if not got or len(bad) >= 2 + len(got.get("segments") or []) or "segments" in bad else "mixed"
    fill = lambda t, m: fan._fill(t, m, lang, ctx.meta)
    return {"studio_version": STUDIO_VERSION, "lang": lang, "opening": fill(opening, vm), "closing": fill(closing, vm) if closing else "", "source": source,
            "segments": [{"fact_id": f["fact_id"], "kind": f["kind"], "t_s": f["t_s"], "minute": f["metrics"]["minute"]["value"], "team": f["team"],
                          "text": fill(t, f["metrics"])} for f, t in segs]}


def write_script(facts, ctx, lang, write, judge):
    """-> (script, warnings): write, review, one revision with the reasons, then each part still rejected is replaced alone. Mirrors the fan view."""
    b = {**brief(facts, ctx, lang), "language": "Spanish" if lang == "es" else "English"}
    try:
        got = write(b, lang) or {}
        bad = _review(facts, ctx, got, lang, b, judge) if got else {}
        if got and bad:
            parts = {"opening": got.get("opening"), "closing": got.get("closing"), **{x.get("fact_id"): x.get("text") for x in got.get("segments") or []}}
            fixed = write(b, lang, [{"part": k, "text": parts.get(k), "reason": r} for k, r in bad.items()]) or {}
            if fixed:
                got, bad = fixed, _review(facts, ctx, fixed, lang, b, judge)
    except Exception as err:  # a failing LLM never fails the job
        return script(facts, ctx, None, lang), [f"studio {lang}: agent failed ({err}); fallback used"]
    warnings = [f"studio {lang}: {k} rejected twice ({r}); replaced" for k, r in bad.items()] if got else []
    return script(facts, ctx, got or None, lang, bad), warnings


def run(match_dir, agent=None, judge=None):
    """-> warnings. Writes personalize/studio/<lang>.json for every language (needs personalize/fan/facts.json)."""
    facts = read_json(os.path.join(match_dir, "personalize", "fan", "facts.json"))
    ctx = fan.Ctx(facts, read_json(os.path.join(match_dir, "roster.json"))["players"], read_json(os.path.join(match_dir, "meta.json")))
    d, warnings = os.path.join(match_dir, "personalize", "studio"), []
    os.makedirs(d, exist_ok=True)
    for lang in LANGS:
        out, w = write_script(facts, ctx, lang, agent or studio_agent.write, judge or fan_judge.judge)
        warnings += w
        write_atomic(os.path.join(d, f"{lang}.json"), json.dumps(out, ensure_ascii=False, indent=1))
    return warnings
