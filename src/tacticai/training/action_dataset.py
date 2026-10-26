"""Build the VAEP action dataset: many headless engine jobs, `analyze` with xG and xPass, one row per action with features and labels -> actions.jsonl, jobs.jsonl, summary.json, README.md."""
import json
import os
import tempfile
import time
from collections import Counter
from multiprocessing import Pool

from ..ingest.application.generate_match import generate_from_recipe
from ..ingest.domain.recipe import to_dict
from ..core.files import read_json, read_jsonl, write_json
from ..interpret.domain import vaep
from ..interpret.application.analyze_match import analyze
from .shot_dataset import make_recipe
from ..interpret.application.models import load_xg

FULL_SEED, SITUATION_SEED = 2000, 60000  # v3 uses 1000.. and 50000..
XG_PATH, XPASS_PATH = "src/tacticai/interpret/models/xg_v1.json", "src/tacticai/interpret/models/xpass_v1.json"

FIELDS = [  # (name, unit, definition)
    ("match_id", "-", "Match package id (recipe_<mode>_<seed>)."), ("job_seed", "-", "Engine seed of the job that produced the row."), ("job_kind", "-", "full_match or situation."),
    ("type", "-", "Action type: pass, interception (credited to the interceptor's team at the pass end point), tackle or shot."),
    ("scores", "bool", "Label: the team of a_i scores after any action in i..i+10 (same period, inside the clip)."),
    ("concedes", "bool", "Label: the rival of the team of a_i scores after any action in i..i+10 (same period, inside the clip)."),
    ("seconds", "s", "Seconds between a_{i-2} and a_i."), ("score_diff", "goals", "Score of the team of a_i minus the rival's, just before a_i."),
    ("xg", "prob", "Engine xG of a_i if it is a shot, else 0."),
    ("a{k}_pass / _interception / _tackle / _shot", "bool", "One-hot action type of a_{i-k} (k = 0, 1, 2; a_{i-k} repeats the earliest action of the period when there are fewer)."),
    ("a{k}_success", "bool", "Pass complete, shot is a goal (tackle and interception are always 1)."),
    ("a{k}_xa, a{k}_ya", "m", "Start position relative to the team of a_i (xa towards the rival goal, ya sign flipped for away)."),
    ("a{k}_end_xa, a{k}_end_ya", "m", "End position, same frame (equal to the start for tackle and interception)."),
    ("a{k}_dist, a{k}_end_dist", "m", "Distance from the start / end to the centre of the rival goal line."),
    ("a{k}_angle, a{k}_end_angle", "rad", "Angle subtended by the two posts from the start / end."),
    ("a{k}_dx", "m", "end_xa - xa."), ("a{k}_same_team", "bool", "a_{i-k} is by the same team as a_i."),
]


def run_job(job):
    kind, seed = job
    recipe = make_recipe(kind, seed)
    xg = load_xg(XG_PATH) if os.path.exists(XG_PATH) else None
    xpass = load_xg(XPASS_PATH) if os.path.exists(XPASS_PATH) else None
    with tempfile.TemporaryDirectory() as tmp:  # tracking goes away with the temp dir
        try:
            out = generate_from_recipe(recipe, seed, tmp, render=False)[0]
        except RuntimeError as err:
            return [], {"seed": seed, "kind": kind, "error": str(err)}
        meta = read_json(os.path.join(out, "meta.json"))
        enriched = read_jsonl(os.path.join(analyze(out, xg_model=xg, xpass_model=xpass), "events_enriched.jsonl"))
    acts = vaep.build_actions(enriched)
    rows = [{"match_id": meta["match_id"], "job_seed": seed, "job_kind": kind, **r} for r in vaep.dataset_rows(acts, meta["pitch"]["length_m"])]
    return rows, dict(seed=seed, kind=kind, recipe=to_dict(recipe), actions=len(rows), goals=sum(e["type"] == "goal" for e in enriched),
                      scores=sum(r["scores"] for r in rows), concedes=sum(r["concedes"] for r in rows))


def readme(summary):
    lines = [
        "# Action dataset actions_v1: VAEP training rows", "",
        "One row per action (pass, interception, tackle, shot) of synthetic matches and situations, with the game-state features of the last three actions and the labels scores / concedes within the next 10 actions. All data is synthetic, produced by the tacticAI engine; none of it is real football.", "",
        "Actions come from `interpret/events_enriched.jsonl` (events detected by Ingest, xG and xPass of the engine). There are no dribbles or carries because Ingest does not detect them. Coordinates are relative to the team of a_i. Labels never cross a period change or the end of the clip.", "",
        "## Generation", "", f"- Parameters: {json.dumps(summary['params'])}",
        f"- Full matches: seeds {FULL_SEED}.., random formation, style and level in [0.7, 1.0] per team. Situations: seeds {SITUATION_SEED}.. (300 steps). Same recipe generator as dataset v3, new seeds.",
        "- Headless engine, `generate_from_recipe(render=False)`, then `analyze` with the xG and xPass models; tracking is deleted after the actions are extracted.", "",
        "## Counts", "", f"- Jobs: {summary['jobs']} ({summary['jobs_failed']} failed with an engine error)", f"- Actions: {summary['actions']}, by type: {json.dumps(summary['by_type'])}",
        f"- scores: {summary['scores']}, concedes: {summary['concedes']}", "",
        "## Files", "", "- `actions.jsonl`: one action per line. `jobs.jsonl`: one line per job. `summary.json`: totals.", "",
        "## Fields", "", "| field | unit | definition |", "|---|---|---|"]
    return "\n".join(lines + [f"| {n} | {u} | {d} |" for n, u, d in FIELDS]) + "\n"


def build(matches, situations, workers, out):
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    jobs = [("full_match", FULL_SEED + i) for i in range(matches)] + [("situation", SITUATION_SEED + i) for i in range(situations)]
    by_type, n, sc, co, failed = Counter(), 0, 0, 0, 0
    with Pool(workers, maxtasksperchild=1) as p, open(os.path.join(out, "actions.jsonl"), "w") as af, open(os.path.join(out, "jobs.jsonl"), "w") as jf:
        for rows, info in p.imap_unordered(run_job, jobs):
            af.writelines(json.dumps(r) + "\n" for r in rows)
            jf.write(json.dumps(info) + "\n")
            af.flush(), jf.flush()
            n, sc, co, failed = n + len(rows), sc + sum(r["scores"] for r in rows), co + sum(r["concedes"] for r in rows), failed + ("error" in info)
            by_type.update(r["type"] for r in rows)
            print(f"{n} actions, {sc} scores, {co} concedes, {failed} failed, {time.time() - t0:.0f}s", flush=True)
    summary = dict(params=dict(matches=matches, situations=situations, workers=workers), jobs=len(jobs), jobs_failed=failed, actions=n,
                   by_type=dict(by_type), scores=sc, concedes=co, elapsed_s=round(time.time() - t0, 1))
    write_json(os.path.join(out, "summary.json"), summary)
    with open(os.path.join(out, "README.md"), "w") as f:
        f.write(readme(summary))
    return summary
