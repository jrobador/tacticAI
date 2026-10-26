import argparse
import json

from ..application.build_personalize import run


def main():
    ap = argparse.ArgumentParser(prog="python -m tacticai.personalize")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="write <match_dir>/personalize/ (18 variants, 18 recaps) from explain/insights.jsonl")
    b.add_argument("match_dir")
    a = ap.parse_args()
    print(json.dumps({"warnings": run(a.match_dir)}))
