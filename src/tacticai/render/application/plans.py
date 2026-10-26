"""Render plans: <match>/explain/insights.jsonl -> <match>/render/plans/<lens>_<club>.json (12 files). Agent plan if it validates, else the rules plan."""
import json
import os

from ...explain.application.build_insights import build_match_context
from ...core.files import read_jsonl, write_atomic
from ..domain import director as D
from . import director_agent

LENSES = ("analyst", "fan", "first_match", "broadcast")
CLUBS = ("neutral", "home", "away")


def director_inputs(insights):
    """-> (rules plan by combo, the Director's input by combo)."""
    rules = {f"{lens}_{club}": D.rules_plan(insights, lens, club) for lens in LENSES for club in CLUBS}
    info = {k: {"threshold": D.THRESHOLD[k.rsplit("_", 1)[0]], "slots": D.SLOTS[k.rsplit("_", 1)[0]], "min_duration_s": D.MIN_DURATION,
                "max_duration_s": D.MAX_DURATION, "rules_plan": r} for k, r in rules.items()}
    return rules, info


def run(match_dir, agent=None, context=None):
    """-> warnings (list of str). `agent` replaces plan_all (tests). A failing agent never fails the job."""
    insights = read_jsonl(os.path.join(match_dir, "explain", "insights.jsonl"))
    agent, warnings = agent or director_agent.plan_all, []
    try:
        ctx = context if context is not None else build_match_context(match_dir)
    except Exception as err:
        ctx = None
        warnings.append(f"render: match context unavailable ({err}); all plans from rules")
    rules, info = director_inputs(insights)
    got = None  # None = no agent plans, silently
    if ctx is not None:
        try:
            got = agent(insights, info, ctx)
            if not isinstance(got, dict):
                raise TypeError(f"returned {type(got).__name__}, expected dict")
        except NotImplementedError:
            got = None
        except Exception as err:
            got = None
            warnings.append(f"render: director failed ({err}); all plans from rules")
    out = os.path.join(match_dir, "render", "plans")
    os.makedirs(out, exist_ok=True)
    for lens in LENSES:
        for club in CLUBS:
            key = f"{lens}_{club}"
            plan, source = rules[key], "rules"
            if got is not None:
                errs = ["missing"] if key not in got else D.validate_plan(got[key], insights, lens) or ([] if got[key] else ["empty plan"])
                if errs:
                    warnings.append(f"render: {key} agent plan rejected ({'; '.join(errs)})")
                else:
                    plan, source = got[key], "agent"
            plan = sorted(plan, key=lambda o: next(i["show_t_s"] for i in insights if i["insight_id"] == o["insight_id"]))
            write_atomic(os.path.join(out, f"{key}.json"),
                          json.dumps({"plan_version": 1, "lens": lens, "club": club, "source": source, "overlays": plan}, indent=2))
    return warnings
