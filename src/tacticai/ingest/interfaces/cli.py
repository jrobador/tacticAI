import argparse
import json
import sys

from ..application.generate_match import generate_match
from ..application.infer_events import infer_events
from ..domain.clock import STEPS_PER_MATCH
from ..domain.events import DEFAULTS


def main():
    ap = argparse.ArgumentParser(prog="python -m tacticai.ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="simulate one match (run inside the engine Docker image)")
    g.add_argument("--seed", type=int, required=True)
    g.add_argument("--steps", type=int, default=STEPS_PER_MATCH)
    g.add_argument("--out", default="data/matches")
    e = sub.add_parser("events", help="infer events from a match's tracking.jsonl")
    e.add_argument("match_dir")
    for k, v in DEFAULTS.items():
        e.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)
    a = ap.parse_args()
    if a.cmd == "generate":
        try:
            out, rows, frames, mp4_frames = generate_match(a.seed, a.steps, a.out)
        except RuntimeError as err:
            sys.exit(f"ERROR: {err}")
        if mp4_frames != frames:
            print(f"WARNING: mp4 has {mp4_frames} frames but {frames} were written", file=sys.stderr)
        print(f"done: {out} steps={rows} frames={frames} mp4_frames={mp4_frames}")
    else:
        print(json.dumps(infer_events(a.match_dir, {k: getattr(a, k) for k in DEFAULTS}), indent=2))
