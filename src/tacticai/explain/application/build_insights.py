"""Explain stage: <match>/interpret -> <match>/explain/insights.jsonl + meta.json. Deterministic; the Explainer agent only writes text and any failure falls back to templates."""
import json
import os

from ...core.files import read_json, read_jsonl, write_atomic
from ..domain import importance, moments, placeholders as P
from . import explainer_agent

FORMAT_VERSION = 1


def _opt(path, read):
    return read(path) if os.path.exists(path) else None


def build_insights(match_dir):
    """-> insights (no `text`) with ids i000.. ordered by show_t_s; each has metrics, refs, claims, importance and agent_context."""
    i = lambda f: os.path.join(match_dir, "interpret", f)
    notes, seqs, events = read_jsonl(i("tactical_notes.jsonl")), read_jsonl(i("sequences.jsonl")), read_jsonl(i("events_enriched.jsonl"))
    models = read_json(i("meta.json")).get("models", {})
    cands = moments.detect(notes, seqs, events)
    cands.sort(key=lambda c: (c["show_t_s"], c["t_s"], c["kind"], c["team"], c["subtype"], c["refs"]["note_index"] if c["refs"]["note_index"] is not None else -1))
    moments.with_agent_context(cands, _opt(i("agents.json"), read_json), _opt(i("phases.jsonl"), read_jsonl))
    out = []
    for k, (c, imp) in enumerate(zip(cands, importance.rate(cands, events, models.get("vaep") is not None))):
        d = {"insight_id": f"i{k:03d}", **{n: c[n] for n in ("kind", "subtype", "team", "players", "t_s", "until_t_s", "show_t_s", "clock_s", "period", "metrics", "refs", "claims")},
             "importance": imp, "agent_context": c["agent_context"]}
        out.append(d)
    return out


def build_match_context(match_dir):
    """Tactics.match_context() + teams + projection + roster (same dict for Explainer, Lens, Recap and Director)."""
    from ...interpret.application.tactics_tools import Tactics, load_match
    m = load_match(match_dir)
    ctx = Tactics(m).match_context()
    return {**ctx, "teams": m["meta"]["teams"], "projection": m["analysis"].get("projection"),
            "roster": {pid: {"name": p["name"], "number": p["number"], "role": p["role"], "team": p["team"]} for pid, p in m["roster"].items()}}


# ---- templates (English, neutral perspective, placeholders only) -----------------------------------------------------------------------------------------------------------------------

_END = {"goal": "The move ended in a goal", "shot": "The move ended in a shot", "lost": "The move ended with the ball lost",
        "out": "The move ended with the ball out of play", "end_of_period": "The move ran until the end of the period"}


def template(c, names):
    """-> (fact, why) for an insight (a dict with kind, subtype, team, metrics, claims). Only placeholders that exist in `metrics`."""
    T, k, s, m, cl = names[c["team"]], c["kind"], c["subtype"], c["metrics"], c["claims"]
    xg = " ({xg} engine xG)" if "xg" in m else ""
    if k == "lines_broken":
        return f"{T} broke {{lines_broken}} lines in {{passes}} passes", _END.get(s, "The move ended") + (xg if s in ("goal", "shot") else "")
    if k == "pressure_spell":
        if s == "peak":
            return f"{T} reached a pressure of {{value}}", ("Its highest pressure of the match" if "match_max" in cl else "Pressure well above its usual level") + ", with a match mean of {match_mean}"
        return (f"{T} {'raised' if s == 'shift_up' else 'lowered'} its pressure from {{before}} to {{after}}", "The change held over a sustained spell")
    if k == "goal_or_chance":
        why = ("It opened the scoring" if "first_goal" in cl else "It levelled the score" if "equaliser" in cl else f"It put {T} ahead" if "go_ahead" in cl else "It changed the score")
        if s == "goal":
            return (f"{T} scored" + (" from a shot worth {xg} engine xG" if "xg" in m else ""), why)
        return (f"{T} {'scored from' if s == 'chance_scored' else 'created'} a big chance worth {{xg}} engine xG", "The shot ended in a goal" if s == "chance_scored" else "The shot did not end in a goal")
    if s == "swing":
        return f"Momentum swung to {T}, from {{before}} to {{after}}", "The balance of the match changed over a sustained spell"
    return f"{T} dominated a spell with a mean momentum of {{mean_momentum}}", "It produced {xg} engine xG and {final_third_entries} entries into the final third"


def explain_all(insights, ctx, names, agent=None):
    """Adds `text` {fact, why, source} to each insight, in place. The agent output is validated per insight; anything wrong falls back to the template.
    -> warnings (list of str) for the job message."""
    warnings, got = [], {}
    try:
        got = (agent or explainer_agent.explain_insights)([{k: v for k, v in d.items() if k != "text"} for d in insights], ctx)
        if not isinstance(got, dict):
            raise TypeError(f"explainer returned {type(got).__name__}, expected dict")
    except Exception as err:  # a failing LLM never fails the job
        warnings.append(f"explain: explainer failed ({err}); all texts from templates")
        got = {}
    ids = {d["insight_id"] for d in insights}
    for iid in got:
        if iid not in ids:
            warnings.append(f"explain: explainer returned unknown insight id {iid}")
    for d in insights:
        out, errs = got.get(d["insight_id"]), []
        if out is not None:
            if not isinstance(out, dict) or not all(isinstance(out.get(f), str) for f in ("fact", "why")):
                errs = ["fact and why must be strings"]
            else:
                errs = [e for f in ("fact", "why") for e in P.validate_text(out[f], d["metrics"], d["claims"], "en")]
            if errs:
                warnings.append(f"explain: {d['insight_id']} agent text rejected ({'; '.join(errs)})")
        if out is not None and not errs:
            d["text"] = {"fact": out["fact"], "why": out["why"], "source": "agent"}
        else:
            fact, why = template(d, names)
            d["text"] = {"fact": fact, "why": why, "source": "template"}
            bad = [e for f in (fact, why) for e in P.validate_text(f, d["metrics"], d["claims"], "en")]
            if bad:  # a template bug is a code error, not an LLM failure
                raise ValueError(f"template for {d['insight_id']} ({d['kind']}/{d['subtype']}) invalid: {bad}")
    return warnings



def run(match_dir, agent=None, context=None):
    """Builds the insights of a match, writes <match>/explain/insights.jsonl and meta.json atomically. -> (insights, warnings)."""
    insights = build_insights(match_dir)
    meta = read_json(os.path.join(match_dir, "meta.json"))
    names = {t: meta["teams"][t]["name"] for t in ("home", "away")}
    warnings = explain_all(insights, context if context is not None else build_match_context(match_dir), names, agent)
    sources = {}
    for d in insights:
        sources[d["text"]["source"]] = sources.get(d["text"]["source"], 0) + 1
    out = os.path.join(match_dir, "explain")
    os.makedirs(out, exist_ok=True)
    write_atomic(os.path.join(out, "insights.jsonl"), "".join(json.dumps(d) + "\n" for d in insights))
    write_atomic(os.path.join(out, "meta.json"), json.dumps({"explain_version": FORMAT_VERSION, "constants": {"minute_scale_s": importance.MATCH_S, "decimals": 3},
                                                              "momentum_reviewed": moments.MOMENTUM_REVIEWED, "model": explainer_agent.MODEL, "text_sources": sources}, indent=2))
    return insights, warnings
