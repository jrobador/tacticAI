import argparse
import json

from ..application.build_insights import run


def main():
    ap = argparse.ArgumentParser(prog="python -m tacticai.explain")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="write <match_dir>/explain/ from the analysis package")
    b.add_argument("match_dir")
    a = ap.parse_args()
    insights, warnings = run(a.match_dir)
    kinds = {}
    for d in insights:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    print(json.dumps({"insights": len(insights), "by_kind": kinds, "warnings": warnings}))
