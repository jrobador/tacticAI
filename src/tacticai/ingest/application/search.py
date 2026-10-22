"""Seed search: run a recipe over many seeds headless, keep the best one, optionally render it."""
import hashlib
import os
import tempfile
import time
from multiprocessing import Pool

from ..domain.evaluate import evaluate
from ..domain.recipe import from_dict, to_dict
from ..infrastructure.files import read_json, read_jsonl, write_json
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


def search(recipe, out_root, workers=4, render_winner=True, frame_timeout=60.0):
    """Returns (winner dir or None, report). Winner = best score among runs that met every boolean predicate."""
    t0 = time.time()
    base = recipe.seed or 0
    seeds = list(range(base, base + recipe.seeds))
    d = to_dict(recipe)
    with Pool(workers, maxtasksperchild=1) as p:
        results = sorted(p.map(_try, [(d, s) for s in seeds], chunksize=1), key=lambda r: r["seed"])
    good = [r for r in results if "error" not in r and r["ok"]]
    best = min(good, key=lambda r: (-r["score"], r["seed"]), default=None)
    report = {"recipe": d, "seeds": seeds, "results": results, "winner": best and best["seed"]}
    path = os.path.join(out_root, f"search_{recipe.mode}_{base}.json")
    out = None
    if best and render_winner:
        out = generate_from_recipe(recipe, best["seed"], out_root, render=True, frame_timeout=frame_timeout)[0]
        report["render_matches_headless"] = _sha256(os.path.join(out, "tracking.jsonl")) == best["tracking_sha256"]
        path = os.path.join(out, "search_report.json")
    report["elapsed_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json(path, report)
    return out, report
