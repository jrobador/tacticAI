"""Tactical Analyst: one agent run per match; the model picks and words, the code validates and writes interpret/agents.json.
The model never writes a digit: it cites values as placeholders {call_id:path} taken from the citable lists; the code fills in value and evidence."""
import functools
import json
import os
import re

from pydantic import BaseModel
from typing_extensions import TypedDict

from ...agents import foundry
from ...core.files import read_jsonl
from ...explain.domain.placeholders import NUMBER_WORDS
from ..domain.agent_check import check_tactical, citable_text, leaves, resolve_text
from .tactics_tools import Tactics, load_match

TOOL_CAP, TIMEOUT_S = 8, 120

INSTRUCTIONS = """You are a football tactical analyst. The match was already analysed by deterministic tools. You choose, rank and word; you never compute.

The first message has c1 match_context, c2 possession_analysis(phase_candidates) and c3 tactical_evidence(notes). Each has its response and a "citable" list of "key = value" lines. You may call more tools (match_context, tactical_evidence, team_shape, pressing_profile, compare_metrics, possession_analysis, player_profile); each result has the same format. At most {remaining} more calls, no repeated questions. Differences, percentages and rankings come only from compare_metrics.

Deliver, in English:
- phases: at most 3, each a candidate from c2 by its candidate_id. Only ids that appear in c2; never label a stretch without a candidate. No candidates in c2: no phases.
- key_notes: at most 5, each a note from c3 by its note_index. Only indexes that appear in c3.
- Rank each list 1, 2, 3... by importance, no repeats.
- summary: 2-3 sentences connecting the phases and notes.

Numbers (the most important rule):
- You never write a digit or a number word (forbidden: {number_words}). A number can only be a placeholder with the exact key from a citable list, in curly braces. The code fills in the value.
- A phase text describes the phase in words and has at most ONE placeholder. A key note text has at most TWO. The summary has NO numbers at all.
- Never mention durations, distances, times, scores or counts of passes, entries, lines, players or shots in any other form. When in doubt, no number: say "a high pressure peak", "both teams", "a single pass", "an early chance".
- Only keys that appear in the citable lists; a missing key makes the text invalid.
- Say home or away team, never player ids.

Good output:
phase: candidate_id 0, "The home team won the ball and ran a counter that gained {{c2:results.home.phase_candidates.items.0.values.gain_m}} m."
key note: note_index 5, "A big chance was scored by a home player, with an engine xG of {{c3:results.all.notes.items.5.evidence.xg}}."
summary: "The home team's counter led to a big chance and a goal, while the away team answered with a pressure peak."
Invalid: "a line-breaking pass sequence of two passes over five seconds gained 21 metres" (number word, number word, digits: use at most one placeholder or no number).

Data limits: relative physics only (no km, no fatigue); xG and xPass are engine values; no Premier League comparisons; no causality, only association in time ("because", "led to", "caused" are not allowed)."""


class Phase(BaseModel):
    candidate_id: int
    rank: int
    text: str


class KeyNote(BaseModel):
    note_index: int
    rank: int
    text: str


class Summary(BaseModel):
    text: str


class Tactical(BaseModel):
    phases: list[Phase]
    key_notes: list[KeyNote]
    summary: Summary


class Interval(TypedDict, total=False):
    from_t_s: float
    until_t_s: float


def _with_citable(tool):
    """What the model gets back from a tool: {"call_id", "response", "citable": "key = value" lines}; the ToolLog keeps the raw response."""
    @functools.wraps(tool)
    def view(**kw):
        r = tool(**kw)
        cid = r.get("call_id")
        if cid is None:
            return r
        resp = {k: v for k, v in r.items() if k != "call_id"}
        return {"call_id": cid, "response": resp, "citable": citable_text(leaves(cid, resp))}
    return view


def _tools(t, log):
    """Typed wrappers over the Tactics methods: the framework builds the model's JSON schema from these signatures (the methods are untyped)."""
    def keep(**kw):
        return {k: v for k, v in kw.items() if v is not None}

    def match_context(team: str | None = None, from_t_s: float | None = None, until_t_s: float | None = None) -> dict:
        """Score, effective time, possession, shots, engine xG, quality and available metrics. team: home or away; omit for both."""
        return t.match_context(**keep(team=team, from_t_s=from_t_s, until_t_s=until_t_s))

    def tactical_evidence(kind: str = "notes", team: str | None = None, from_t_s: float | None = None, until_t_s: float | None = None,
                          limit: int | None = None, cursor: int | None = None) -> dict:
        """Tactical notes, events, sequences or windows. kind: notes, events, sequences or windows; cursor = offset for the next page."""
        return t.tactical_evidence(**keep(kind=kind, team=team, from_t_s=from_t_s, until_t_s=until_t_s, limit=limit, cursor=cursor))

    def team_shape(team: str | None = None, from_t_s: float | None = None, until_t_s: float | None = None, metrics: list[str] | None = None,
                   in_possession: bool | None = None) -> dict:
        """Block height, defensive line, length, width, occupation, block band. metrics: any of block_height, defensive_line, length, width, occupation, block_band."""
        return t.team_shape(**keep(team=team, from_t_s=from_t_s, until_t_s=until_t_s, metrics=metrics, in_possession=in_possession))

    def pressing_profile(team: str | None = None, from_t_s: float | None = None, until_t_s: float | None = None, metrics: list[str] | None = None) -> dict:
        """Pressure, pressing episodes, high press, recoveries, PPDA proxy. metrics: any of pressure, pressures, high_press, recoveries, high_regains, press_outcomes, ppda_proxy."""
        return t.pressing_profile(**keep(team=team, from_t_s=from_t_s, until_t_s=until_t_s, metrics=metrics))

    def compare_metrics(metric_ids: list[str], subject: str, interval_a: Interval, interval_b: Interval | None = None, reference: str = "match") -> dict:
        """The only source of differences, ratios and percentages: interval a vs b for each metric id. subject: home or away. Without interval_b, reference is match (whole match, same team) or opponent (other team, same interval). Metric ids: block_height, defensive_line, length, width, pressure, pressures_per_min, high_press_s, high_regains, recoveries_total, press_recovery_rate, ppda_proxy, possession_pct, shots, xg."""
        return t.compare_metrics(**keep(metric_ids=metric_ids, subject=subject, interval_a=interval_a, interval_b=interval_b, reference=reference))

    def possession_analysis(team: str | None = None, from_t_s: float | None = None, until_t_s: float | None = None, metrics: list[str] | None = None) -> dict:
        """Possessions, build-up, transitions, counters and phase candidates. metrics: any of possessions, build_up, attacking_transitions, defensive_transitions, counters, phase_candidates."""
        return t.possession_analysis(**keep(team=team, from_t_s=from_t_s, until_t_s=until_t_s, metrics=metrics))

    def player_profile(player_id: str | None = None, team: str | None = None, limit: int | None = None) -> dict:
        """Rating of one player (player_id) or the ranking of a team's players, with the breakdown."""
        return t.player_profile(**keep(player_id=player_id, team=team, limit=limit))

    fns = (match_context, tactical_evidence, team_shape, pressing_profile, compare_metrics, possession_analysis, player_profile)
    return [_with_citable(log.wrap(f)) for f in fns]


def _write_agents(interpret, tactical):
    path, tmp = os.path.join(interpret, "agents.json"), os.path.join(interpret, "agents.json.tmp")
    doc = {"agents_version": 1, "model": os.environ["FOUNDRY_DEPLOYMENT"], "quality": None, "tactical": tactical}
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entry_view(e):
    resp = json.dumps(e["response"], ensure_ascii=False, separators=(",", ":"), default=str)
    return f"{e['call_id']} {e['tool']} {json.dumps(e['args'])}\nresponse: {resp}\ncitable:\n{citable_text(leaves(e['call_id'], e['response']))}"


def _build(out, log, n_phases, n_notes):
    """Resolves the placeholders, drops the items that fail (re-ranking the rest) and runs check_tactical as the final guard. Returns (tactical, warnings)."""
    cited = {}
    for e in log.entries:
        cited.update(leaves(e["call_id"], e["response"]))
    warnings, block = [], {"phases": [], "key_notes": []}
    for name in block:
        for i, it in enumerate(sorted(getattr(out, name), key=lambda x: x.rank)):
            text, evidence, errs = resolve_text(it.text, cited)
            if errs:
                warnings.append(f"tactical agent: dropped {name}[{i}] ({errs[0]})")
            else:
                block[name].append({**it.model_dump(exclude={"text", "rank"}), "text": text, "evidence": evidence})
    text, evidence, errs = resolve_text(out.summary.text, cited)
    if errs:
        raise ValueError(f"summary: {errs[0]}")
    block["summary"] = {"text": text, "evidence": evidence}

    def ranked():
        return {**block, **{n: [{**x, "rank": r} for r, x in enumerate(block[n], 1)] for n in ("phases", "key_notes")}}
    while errors := check_tactical(ranked(), log.entries, n_phases, n_notes):
        bad = {(m.group(1), int(m.group(2))) for m in (re.match(r"(phases|key_notes)\[(\d+)\]", x) for x in errors) if m}
        if not bad:
            raise ValueError("; ".join(errors[:5]))
        for name, i in sorted(bad, reverse=True):
            why = next(x for x in errors if x.startswith(f"{name}[{i}]")).split(": ", 1)[1]
            warnings.append(f"tactical agent: dropped {name}[{i}] ({why})")
            del block[name][i]
    block = ranked()
    if (n_phases or n_notes) and not block["phases"] and not block["key_notes"]:
        raise ValueError("no valid phase or key note: " + "; ".join(warnings))
    return block, warnings


def run_agents(match_dir):
    """Returns the warnings for the job's message; never raises. Writes interpret/agents.json only when the output validates."""
    if not foundry.configured():
        return ["agents not implemented"]
    interpret, log = os.path.join(match_dir, "interpret"), foundry.ToolLog(cap=TOOL_CAP)
    try:
        t = Tactics(load_match(match_dir))
        pre = [log.call("match_context", t.match_context), log.call("possession_analysis", t.possession_analysis, metrics=["phase_candidates"]),
               log.call("tactical_evidence", t.tactical_evidence, kind="notes")]
        n_phases, n_notes = (len(read_jsonl(os.path.join(interpret, f))) for f in ("phases.jsonl", "tactical_notes.jsonl"))
        message = "\n\n".join(_entry_view(e) for e in pre) + f"\n\nValid candidate_id values: 0..{n_phases - 1}. Valid note_index values: 0..{n_notes - 1}."
        out = foundry.run(INSTRUCTIONS.format(remaining=TOOL_CAP - len(pre), number_words=", ".join(NUMBER_WORDS["en"])), message,
                          tools=_tools(t, log), response_format=Tactical, timeout_s=TIMEOUT_S, max_tool_calls=TOOL_CAP, max_output_tokens=2000)
        tactical, warnings = _build(out, log, n_phases, n_notes)
        _write_agents(interpret, tactical)
        return warnings
    except Exception as e:
        return [f"tactical agent failed: {type(e).__name__}: {e}"]
    finally:
        try:
            log.write(os.path.join(interpret, "agents_log.jsonl"))
        except Exception:
            pass
