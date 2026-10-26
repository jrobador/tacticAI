import argparse
import json

from .application.plans import run

ap = argparse.ArgumentParser(prog="python -m tacticai.render")
sub = ap.add_subparsers(dest="cmd", required=True)
sub.add_parser("plans", help="write <match_dir>/render/plans/ (12 Director plans)").add_argument("match_dir")
a = ap.parse_args()
print(json.dumps({"warnings": run(a.match_dir)}))
