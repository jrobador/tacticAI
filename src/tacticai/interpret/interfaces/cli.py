import argparse
import json

from ..application.build_shot_dataset import build


def main():
    ap = argparse.ArgumentParser(prog="python -m tacticai.interpret")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("shots", help="build the synthetic kick-candidate dataset (run inside the engine Docker image)")
    s.add_argument("--matches", type=int, default=8, help="full matches, seeds 1000..")
    s.add_argument("--situations", type=int, default=40, help="300-step situations, seeds 50000..")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--out", default="data/datasets/shots_v2")
    a = ap.parse_args()
    print(json.dumps(build(a.matches, a.situations, a.workers, a.out), indent=2))
