"""Fan view: <match>/personalize/fan/facts.json (what code detected) and <lang>_<club>.json (6 files: what each supporter reads).

Per view (language x club): code builds the brief (facts + the reader's perspective), the Supporter agent writes it, code checks the
contract (placeholders, claims, names, stance) and the Fan judge checks the rubric (language, stance, facts only, voice, units).
Rejected texts go back to the Supporter once with their reasons; what still fails falls back to a line of data (fan_locale)."""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from ...agents import fan_judge
from ...core.files import read_json, read_jsonl, write_atomic
from ...explain.domain import placeholders as P
from ...interpret.domain import physical
from ..domain import fan_facts, fan_locale as L, fan_perspective as V
from ..domain.lenses import CLUBS, LANGS
from . import supporter_agent

FAN_VERSION = 3
#: Views written at the same time: six Foundry callers at once hit the deployment's token rate limit.
MAX_PARALLEL_VIEWS = 3
#: What a fact may say besides its kind, people and numbers (fan_facts.py), passed to the agent as they are.
FACT_DETAILS = ("situation", "punished", "threat", "from_own_half", "clear_chance", "alone", "splits_block", "risky")


def _shorts(meta, text):
    return text.replace("{home_short}", meta["teams"]["home"]["short"]).replace("{away_short}", meta["teams"]["away"]["short"])


def check(text, metrics, claims, lang, allowed, every_name, meta):
    """Contract errors of one text, the same rules as the rest of the pipeline: placeholders only for numbers, claim words only with their
    claim, and no name outside the item's own. Language, stance, invented facts and voice are the Fan judge's."""
    if not isinstance(text, str) or not text.strip():
        return ["empty text"]
    t = _shorts(meta, text)
    errors = P.validate_text(t, metrics, claims, lang)
    errors += [f"name {n!r} is not part of this item" for n in every_name if n not in allowed and re.search(rf"(?<!\w){re.escape(n)}(?!\w)", t)]
    return errors


def _fill(text, metrics, lang, meta):
    return P.resolve_text(_shorts(meta, text), metrics, lang=lang)


def _ph(metrics, skip=()):
    return [f"{{{k}}}" for k in metrics if k not in skip]


class Ctx:
    """What every view of a match shares: facts, names and sides."""

    def __init__(self, facts, roster, meta):
        self.facts, self.meta = facts, meta
        self.players = {p["player_id"]: p["name"] for p in roster}
        self.team_of = {p["player_id"]: p["team"] for p in roster}
        self.teams = {s: meta["teams"][s]["name"] for s in ("home", "away")}
        self.every = list(self.players.values()) + list(self.teams.values())


def slots(ctx, lang, club):
    """Every text a reader of (lang, club) sees, as a slot: id, where the agent's answer is, its brief item, contract and fallback."""
    f_, n, out = ctx.facts, ctx.players, []
    rel = lambda side: V.relation(side, club)
    teams = list(ctx.teams.values())
    for f in f_["facts"]:
        people = [{"name": n[p["player_id"]], "role": p["role"], "side": rel(p["side"])} for p in V.player_roles(f, ctx.team_of)]
        st = V.stance(f, club)
        item = {"fact_id": f["fact_id"], "kind": f["kind"], "team": ctx.teams[f["team"]], "stance": st, "meaning": V.MEANING[st], "people": people,
                **({"shot_from": L.SHOT_FROM[lang][f["where"]]} if f.get("where") else {}),
                **{k: f[k] for k in FACT_DETAILS if f.get(k) is not None},
                "claims": f["claims"], "placeholders": _ph(f["metrics"], ("minute",)) + ["{home_short}", "{away_short}"]}
        out.append({"id": f"m:{f['fact_id']}", "key": ("moments", f["fact_id"]), "brief": item, "metrics": f["metrics"], "claims": f["claims"],
                    "allowed": [x["name"] for x in people] + teams, "stance": st,
                    "fallback": list(L.moment(f, [x["name"] for x in people] or [ctx.teams[f["team"]]], lang))})
        facts_of_moment = {k: item[k] for k in ("kind", "people", "shot_from", *FACT_DETAILS) if k in item}
        for p in V.player_roles(f, ctx.team_of):
            out.append({"id": f"p:{p['player_id']}:{f['fact_id']}", "key": ("player_lines", (p["player_id"], f["fact_id"])),
                        "brief": {"player_id": p["player_id"], "fact_id": f["fact_id"], "name": n[p["player_id"]], "role": p["role"], "side": rel(p["side"]),
                                  "moment": facts_of_moment, "stance": st, "meaning": V.MEANING[st], "placeholders": _ph(f["metrics"], ("minute",))},
                        "metrics": f["metrics"], "claims": f["claims"], "allowed": [x["name"] for x in people] + teams, "fallback": None})
    v = f_["verdict"]
    res = V.result(v["winner"], club)
    vm = {k: v["metrics"][k] for k in ("home_goals", "away_goals")}
    figure = n.get(v["figure"]) if v["figure"] else None
    out.append({"id": "v", "key": ("verdict",), "metrics": vm, "claims": v["claims"], "allowed": teams + ([figure] if figure else []),
                "brief": {"result": res, "winner": ctx.teams.get(v["winner"]), "deserved": v["deserved"], "figure": figure,
                          "placeholders": _ph(vm) + ["{home_short}", "{away_short}"]},
                "fallback": list(L.verdict(res, ctx.teams.get(v["winner"]), figure, lang))})
    for r in f_["ratings"]:
        name = n[r["player_id"]]
        out.append({"id": f"r:{r['player_id']}", "key": ("ratings", r["player_id"]), "metrics": r["metrics"], "claims": r["claims"],
                    "allowed": [name, ctx.teams[r["team"]]], "fallback": [L.rating(r, lang)],
                    "brief": {"player_id": r["player_id"], "name": name, "side": rel(r["team"]), "rating": L.BAND[lang][r["band"]], "claims": r["claims"],
                              "placeholders": _ph(r["metrics"])}})
    for a in f_.get("awards", []):
        name = n[a["player_id"]]
        out.append({"id": f"a:{a['award']}", "key": ("awards", a["award"]), "metrics": {}, "claims": [], "allowed": [name, ctx.teams[a["team"]]],
                    "fallback": [""], "brief": {"award": a["award"], "title": L.AWARD[lang][a["award"]][0], "name": name, "side": rel(a["team"])}})
    # A question claims nothing: it may name any player and ask about an opener or an equaliser.
    out.append({"id": "ask:all", "key": ("ask_examples",), "metrics": {}, "claims": list(P.CLAIM_WORDS), "allowed": ctx.every, "fallback": list(L.ASK[lang]), "brief": {}})
    return out


def brief(ctx, lang, club, items):
    """What the Supporter agent receives for one view: the reader and every slot's brief, grouped as its output is."""
    group = {"moments": [], "player_lines": [], "verdict": None, "ratings": [], "awards": []}
    for s in items:
        k = s["key"][0]
        if k == "verdict":
            group["verdict"] = s["brief"]
        elif k in group:
            group[k].append(s["brief"])
    reader = "a passionate neutral" if club == "neutral" else f"a supporter of {ctx.teams[club]} ({ctx.meta['teams'][club]['short']})"
    return {"language": "Spanish (Rioplatense)" if lang == "es" else "English", "reader": reader,
            "teams": {s: {"name": ctx.teams[s], "short": ctx.meta["teams"][s]["short"]} for s in ("home", "away")}, **group}


def _texts(got, slot):
    """The agent's texts for a slot, or None."""
    k = slot["key"]
    if k[0] == "moments":
        m = (got.get("moments") or {}).get(k[1])
        return [m.get("title"), m.get("text")] if m else None
    if k[0] == "verdict":
        v = got.get("verdict")
        return [v.get("headline"), v.get("text")] if v else None
    if k[0] == "ask_examples":
        a = got.get("ask_examples") or []
        return list(a[:3]) if len(a) >= 3 else None
    x = (got.get(k[0]) or {}).get(k[1])
    return [x] if x else None


def _contract(got, slot, lang, ctx):
    texts = _texts(got, slot)
    if not texts or not all(isinstance(t, str) for t in texts):
        return None, ["missing"]
    errs = [e for t in texts for e in check(t, slot["metrics"], slot["claims"], lang, slot["allowed"], ctx.every, ctx.meta)]
    want = slot.get("stance")
    if want and (got.get("moments") or {}).get(slot["key"][1], {}).get("stance") != want:
        errs.append(f"written as {(got['moments'][slot['key'][1]]).get('stance')!r}, the reader's stance is {want!r}")
    return texts, errs


def write_view(ctx, lang, club, write=None, judge=None):
    """-> (view, warnings) for one language and club. `write`/`judge` replace the agents (tests)."""
    write, judge = write or supporter_agent.write, judge or fan_judge.judge
    items = slots(ctx, lang, club)
    b = brief(ctx, lang, club, items)
    tag, warnings = f"{lang}_{club}", []
    stats = {"agent": 0, "fallback": 0, "revised": 0}
    try:
        got = write(b, lang) or {}
    except Exception as err:  # a failing LLM never fails the job
        warnings.append(f"fan {tag}: supporter agent failed ({err}); fallback used")
        got = {}
    accepted = {}

    def review(got, pending):
        """Contract, then judge: -> {id: reason} of the rejected among `pending`; accepted texts land in `accepted`."""
        bad, ok = {}, {}
        for s in pending:
            texts, errs = _contract(got, s, lang, ctx)
            if errs:
                bad[s["id"]] = "; ".join(errs)
            else:
                ok[s["id"]] = texts
        if ok and got:
            verdicts = judge([{"id": i, "text": " | ".join(ok[i]), "brief": by_id[i]["brief"]} for i in ok],
                             {"language": b["language"], "reader": b["reader"]})
            bad.update(verdicts)
        for i, texts in ok.items():
            if i not in bad:
                accepted[i] = texts
        return bad

    by_id = {s["id"]: s for s in items}
    bad = review(got, items) if got else {}
    retry = [i for i, r in bad.items() if r != "missing"]
    if retry:
        stats["revised"] = len(retry)
        try:
            fixed = write(b, lang, [{"id": i, "text": " | ".join(_texts(got, by_id[i]) or []), "reason": bad[i]} for i in retry]) or {}
        except Exception as err:
            warnings.append(f"fan {tag}: supporter revision failed ({err})")
            fixed = {}
        still = review(fixed, [by_id[i] for i in retry]) if fixed else {i: bad[i] for i in retry}
        warnings += [f"fan {tag}: {i} rejected twice ({r}); fallback used" for i, r in still.items()]

    def final(s):
        if s["id"] in accepted:
            stats["agent"] += 1
            return [_fill(t, s["metrics"], lang, ctx.meta) for t in accepted[s["id"]]], "agent"
        stats["fallback"] += 1
        return (None if s["fallback"] is None else [_fill(t, s["metrics"], lang, ctx.meta) for t in s["fallback"]]), "fallback"

    f_, moments, player_lines, ratings, awards = ctx.facts, [], {}, [], []
    for f in f_["facts"]:
        (title, text), src = final(by_id[f"m:{f['fact_id']}"])
        moments.append({"fact_id": f["fact_id"], "kind": f["kind"], "tier": f["tier"], "stance": V.stance(f, club), "t_s": f["t_s"], "minute": f["metrics"]["minute"]["value"],
                        "team": f["team"], "players": list(f["players"].values()), "title": title, "text": text, "source": src})
        for pid in f["players"].values():
            s = by_id[f"p:{pid}:{f['fact_id']}"]
            if s["id"] in accepted:
                (line,), _ = final(s)
                player_lines.setdefault(pid, {})[f["fact_id"]] = line
    (headline, vtext), vsrc = final(by_id["v"])
    v = f_["verdict"]
    for r in f_["ratings"]:
        (line,), src = final(by_id[f"r:{r['player_id']}"])
        ratings.append({"player_id": r["player_id"], "name": ctx.players[r["player_id"]], "team": r["team"], "band": r["band"],
                        "label": L.BAND[lang][r["band"]], "line": line, "source": src})
    for a in f_.get("awards", []):
        (line,), src = final(by_id[f"a:{a['award']}"])
        title, stat = L.AWARD[lang][a["award"]]
        awards.append({"award": a["award"], "title": title, "player_id": a["player_id"], "name": ctx.players[a["player_id"]], "team": a["team"],
                       "stat": _fill(stat, a["metrics"], lang, ctx.meta), "line": line, "source": src})
    ask, _ = final(by_id["ask:all"])
    view = {"fan_version": FAN_VERSION, "lang": lang, "club": club, "card_s": f_["card_s"], "moments": moments,
            "verdict": {"headline": headline, "text": vtext, "result": V.result(v["winner"], club), "winner": v["winner"], "deserved": v["deserved"], "source": vsrc},
            "ratings": ratings, "awards": awards, "player_lines": player_lines, "ask_examples": ask, "sources": stats}
    return view, warnings


def load_facts(match_dir):
    events = read_jsonl(os.path.join(match_dir, "interpret", "events_enriched.jsonl"))
    timeline = read_jsonl(os.path.join(match_dir, "interpret", "timeline.jsonl"))
    roster = read_json(os.path.join(match_dir, "roster.json"))["players"]
    path = lambda *p: os.path.join(match_dir, *p)
    sequences = read_jsonl(path("interpret", "sequences.jsonl")) if os.path.exists(path("interpret", "sequences.jsonl")) else []
    stats = read_json(path("interpret", "players.json"))["players"] if os.path.exists(path("interpret", "players.json")) else []
    sprints, rows = [], []
    if os.path.exists(path("tracking.jsonl")) and os.path.exists(path("interpret", "meta.json")):
        rows = read_jsonl(path("tracking.jsonl"))
        clock = {r["t_s"]: r["clock_s"] for r in rows}
        thr = read_json(path("interpret", "meta.json"))["thresholds"]["sprint_speed_m_s"]
        sprints = [{**s, "clock_s": clock[s["t_s"]]} for s in physical.sprint_runs(rows, thr)]
    return fan_facts.detect(events, timeline, roster, sequences, sprints, stats, rows), roster


def run(match_dir, agent=None, judge=None):
    """-> warnings. Writes personalize/fan/facts.json and the 6 views. `agent`/`judge` replace the agents (tests)."""
    facts, roster = load_facts(match_dir)
    ctx = Ctx(facts, roster, read_json(os.path.join(match_dir, "meta.json")))
    combos = [(lang, club) for lang in LANGS for club in CLUBS]
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_VIEWS) as pool:
        done = dict(zip(combos, pool.map(lambda c: write_view(ctx, *c, write=agent, judge=judge), combos)))
    d = os.path.join(match_dir, "personalize", "fan")
    os.makedirs(d, exist_ok=True)
    write_atomic(os.path.join(d, "facts.json"), json.dumps(facts, ensure_ascii=False, indent=1))
    warnings = []
    for (lang, club), (view, w) in done.items():
        warnings += w
        write_atomic(os.path.join(d, f"{lang}_{club}.json"), json.dumps(view, ensure_ascii=False, indent=1))
    return warnings
