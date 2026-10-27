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

EARLY_STOP_WINNERS = 3  # stop after the batch that brings this many ok seeds (not with more_* ranking entries)
SEEDS_PER_WORKER = 5  # batch = workers * this: bounds engine memory a worker accumulates; a dead worker loses only its batch


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


def search(recipe, out_root, workers=4, render_winner=True, frame_timeout=60.0, on_progress=None, on_render=None,
           preview_path=None):
    """Returns (winner dir or None, report). Winner = best score among runs that met every boolean predicate.
    on_progress(done, total) fires after each seed; on_render() right before rendering the winner.
    Stops early once a batch ends with EARLY_STOP_WINNERS ok seeds (report: seeds = those tried, stopped_early)."""
    t0 = time.time()
    base = recipe.seed or 0
    seeds = list(range(base, base + recipe.seeds))
    d = to_dict(recipe)
    # ponytail: no one-task-per-process (max_tasks_per_child is 3.11+); a fresh pool per batch recycles workers
    # so engine memory stays bounded, and a dead worker breaks only its batch (its seeds become errors).
    # Early stop is checked per batch only: a batch in flight is never cut, and without a boolean filter (full_match, empty or only more_* wanted) every seed runs.
    wanted = recipe.situation.wanted if getattr(recipe, "situation", None) else []
    can_stop = bool(wanted) and not any(w.startswith("more_") for w in wanted)  # ranking/no filter: score decides, run all
    results, stopped = [], False
    step = workers * SEEDS_PER_WORKER
    for i in range(0, len(seeds), step):
        batch, done = seeds[i:i + step], set()
        with ProcessPoolExecutor(workers) as ex:
            futs = {}
            try:
                for s in batch:
                    futs[ex.submit(_try, (d, s))] = s
            except BrokenProcessPool:
                pass
            for f in as_completed(futs):
                try:
                    r = f.result()
                except BrokenProcessPool:
                    r = {"seed": futs[f], "error": "worker process died"}
                done.add(futs[f])
                results.append(r)
                if on_progress:
                    on_progress(len(results), len(seeds))
        for s in batch:
            if s not in done:  # submit itself failed on an already-broken pool
                results.append({"seed": s, "error": "worker process died"})
                if on_progress:
                    on_progress(len(results), len(seeds))
        if can_stop and sum("error" not in r and r["ok"] for r in results) >= EARLY_STOP_WINNERS and len(results) < len(seeds):
            stopped = True
            if on_progress:
                on_progress(len(results), len(results))  # the UI bar reaches done == total
            break
    results.sort(key=lambda r: r["seed"])
    good = [r for r in results if "error" not in r and r["ok"]]
    best = min(good, key=lambda r: (-r["score"], r["seed"]), default=None)
    report = {"recipe": d, "seeds": [r["seed"] for r in results], "results": results, "winner": best and best["seed"],
              "stopped_early": stopped}
    path = os.path.join(out_root, f"search_{recipe.mode}_{base}.json")
    out = None
    if best and render_winner:
        if on_render:
            on_render()
        out = generate_from_recipe(recipe, best["seed"], out_root, render=True, frame_timeout=frame_timeout,
                                 preview_path=preview_path)[0]
        report["render_matches_headless"] = _sha256(os.path.join(out, "tracking.jsonl")) == best["tracking_sha256"]
        path = os.path.join(out, "search_report.json")
    report["elapsed_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json(path, report)
    return out, report
