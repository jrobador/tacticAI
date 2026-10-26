"""Seed search: run a recipe over many seeds headless, keep the best one, optionally render it."""
import hashlib
import os
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool

from ..domain.evaluate import evaluate
from ..domain.recipe import from_dict, to_dict
from ...core.files import read_json, read_jsonl, write_json
from .generate_match import generate_from_recipe


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _try(args):
    """(recipe dict, seed) -> headless result with its evaluation; engine failures come back as {"error"}."""
    d, seed = args
    recipe = from_dict(d)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            out = generate_from_recipe(recipe, seed, tmp, render=False)[0]
        except RuntimeError as err:
            return {"seed": seed, "error": str(err)}
        rows, events = read_jsonl(os.path.join(out, "tracking.jsonl")), read_jsonl(os.path.join(out, "events.jsonl"))
        roster = read_json(os.path.join(out, "roster.json"))
        return {"seed": seed, "rows": len(rows), "shots": sum(e["type"] == "shot" for e in events),
                "goals": sum(e["type"] == "goal" for e in events),
                "tracking_sha256": _sha256(os.path.join(out, "tracking.jsonl")),
                **evaluate(recipe, rows, events, roster)}


def search(recipe, out_root, workers=4, render_winner=True, frame_timeout=60.0, on_progress=None, on_render=None):
    """Returns (winner dir or None, report). Winner = best score among runs that met every boolean predicate.
    on_progress(done, total) fires after each seed; on_render() right before rendering the winner."""
    t0 = time.time()
    base = recipe.seed or 0
    seeds = list(range(base, base + recipe.seeds))
    d = to_dict(recipe)
    # ponytail: no one-task-per-process (max_tasks_per_child is 3.11+); a dead worker breaks the pool, so
    # every seed still pending is recorded as an error instead of waiting forever.
    results = []
    with ProcessPoolExecutor(workers) as ex:
        futs = {}
        try:
            for s in seeds:
                futs[ex.submit(_try, (d, s))] = s
        except BrokenProcessPool:
            pass
        done = set()
        for f in as_completed(futs):
            try:
                r = f.result()
            except BrokenProcessPool:
                r = {"seed": futs[f], "error": "worker process died"}
            done.add(futs[f])
            results.append(r)
            if on_progress:
                on_progress(len(results), len(seeds))
        for s in seeds:
            if s not in done:  # submit itself failed on an already-broken pool
                results.append({"seed": s, "error": "worker process died"})
                if on_progress:
                    on_progress(len(results), len(seeds))
    results.sort(key=lambda r: r["seed"])
    good = [r for r in results if "error" not in r and r["ok"]]
    best = min(good, key=lambda r: (-r["score"], r["seed"]), default=None)
    report = {"recipe": d, "seeds": seeds, "results": results, "winner": best and best["seed"]}
    path = os.path.join(out_root, f"search_{recipe.mode}_{base}.json")
    out = None
    if best and render_winner:
        if on_render:
            on_render()
        out = generate_from_recipe(recipe, best["seed"], out_root, render=True, frame_timeout=frame_timeout)[0]
        report["render_matches_headless"] = _sha256(os.path.join(out, "tracking.jsonl")) == best["tracking_sha256"]
        path = os.path.join(out, "search_report.json")
    report["elapsed_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json(path, report)
    return out, report
