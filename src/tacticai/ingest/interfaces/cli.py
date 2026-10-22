import argparse
import json
import os
import sys
from collections import Counter

from ..application.generate_match import generate_from_recipe, generate_match, generate_segment
from ..application.infer_events import infer_events
from ..application.measure_presets import measure, write_doc
from ..application.search import search
from ..domain.clock import STEPS_PER_MATCH
from ..domain.events import DEFAULTS
from ..domain.recipe import RecipeError, from_dict


def main():
    ap = argparse.ArgumentParser(prog="python -m tacticai.ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="simulate one match (run inside the engine Docker image)")
    g.add_argument("--seed", type=int, help="required unless --recipe has a seed")
    g.add_argument("--recipe", help="recipe JSON path (see docs/ingest/engine-reference.md#recipes)")
    g.add_argument("--no-render", action="store_true", help="headless: no video.mp4, no Xvfb needed, much faster")
    g.add_argument("--steps", type=int, help="in-play rows to record (default 3000, 300 for a situation)")
    g.add_argument("--out", default="data/matches")
    g.add_argument("--frame-timeout", type=float, default=60.0, help="seconds without an engine frame before exiting with code 3")
    sg = sub.add_parser("segment", help="render rows [from, to) of a recipe match via state transfer (engine image + Xvfb)")
    sg.add_argument("--recipe", required=True)
    sg.add_argument("--seed", type=int, required=True)
    sg.add_argument("--from", dest="from_step", type=int, required=True)
    sg.add_argument("--to", dest="to_step", type=int, required=True)
    sg.add_argument("--out", default="data/matches")
    sg.add_argument("--frame-timeout", type=float, default=60.0)
    e = sub.add_parser("events", help="infer events from a match's tracking.jsonl")
    e.add_argument("match_dir")
    for k, v in DEFAULTS.items():
        e.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)
    m = sub.add_parser("measure", help="measurement gate: style/formation metrics over headless matches (engine image)")
    m.add_argument("--what", choices=["styles", "formations"], required=True)
    m.add_argument("--seeds", type=int, default=20)
    m.add_argument("--steps", type=int, default=900)
    m.add_argument("--out", help="default data/measure/<what>.json")
    m.add_argument("--doc", default="docs/ingest/presets.md")
    sr = sub.add_parser("search", help="try the recipe's seeds headless and render the best one (engine image)")
    sr.add_argument("--recipe", required=True)
    sr.add_argument("--workers", type=int, default=4)
    sr.add_argument("--no-render", action="store_true", help="do not render the winner")
    sr.add_argument("--out", default="data/matches")
    sr.add_argument("--frame-timeout", type=float, default=60.0)
    a = ap.parse_args()
    if a.cmd == "search":
        return run_search(a)
    if a.cmd == "measure":
        out = a.out or f"data/measure/{a.what}.json"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        measure(a.what, a.seeds, a.steps, out)
        write_doc(os.path.dirname(out), a.doc)
        print(f"done: {out} {a.doc}")
        return
    if a.cmd == "segment":
        try:
            r = from_dict(json.load(open(a.recipe)))
            out, rows, frames, mp4 = generate_segment(r, a.seed, a.from_step, a.to_step, a.out, a.frame_timeout)
        except (RecipeError, RuntimeError) as err:
            sys.exit(f"ERROR: {err}")
        print(f"done: {out} rows={rows} frames={frames} mp4_frames={mp4} (video has frames from frame_index {frames - mp4})")
        return
    if a.cmd == "generate":
        try:
            if a.recipe:
                try:
                    r = from_dict(json.load(open(a.recipe)))
                except RecipeError as err:
                    sys.exit(f"ERROR: invalid recipe: {err}")
                seed = a.seed if a.seed is not None else r.seed
                out, rows, frames, mp4_frames = generate_from_recipe(r, seed, a.out, not a.no_render, a.frame_timeout, a.steps)
            elif a.seed is None:
                sys.exit("ERROR: --seed or --recipe is required")
            else:
                out, rows, frames, mp4_frames = generate_match(a.seed, a.steps or STEPS_PER_MATCH, a.out,
                                                               a.frame_timeout, not a.no_render)
        except RuntimeError as err:
            sys.exit(f"ERROR: {err}")
        if mp4_frames is not None and mp4_frames != frames:
            print(f"WARNING: mp4 has {mp4_frames} frames but {frames} were written", file=sys.stderr)
        print(f"done: {out} steps={rows} frames={frames} mp4_frames={mp4_frames}")
    else:
        print(json.dumps(infer_events(a.match_dir, {k: getattr(a, k) for k in DEFAULTS}), indent=2))


def run_search(a):
    try:
        r = from_dict(json.load(open(a.recipe)))
    except RecipeError as err:
        sys.exit(f"ERROR: invalid recipe: {err}")
    out, rep = search(r, a.out, a.workers, not a.no_render, a.frame_timeout)
    res, wanted = rep["results"], r.situation.wanted if r.situation else []
    met = sum("error" not in x and x["ok"] for x in res)
    line = f"tried {len(res)} seeds in {rep['elapsed_s']} s, {met} met {wanted or 'nothing in particular'}"
    if rep["winner"] is None:
        miss = Counter(m for x in res for m in x.get("missing", []))
        print(f"{line}, no winner; missing most often: {miss.most_common(1)[0][0] if miss else 'n/a (engine errors)'}")
        sys.exit(2)
    w = next(x for x in res if x["seed"] == rep["winner"])
    print(f"{line}, winner seed {w['seed']} (score {w['score']:.2f}), {out or 'not rendered, see search_*.json in ' + a.out}")
    if rep.get("render_matches_headless") is False:
        print("WARNING: rendered tracking.jsonl differs from the headless run of the winner seed", file=sys.stderr)
