import argparse
import json
import os

from ..application.analyze_match import analyze
from ..application.build_shot_dataset import build
from ..application.train_models import load_xg, train, train_xpass

XG_DEFAULT = "src/tacticai/interpret/models/xg_v1.json"
XPASS_DEFAULT = "src/tacticai/interpret/models/xpass_v1.json"


def main():
    ap = argparse.ArgumentParser(prog="python -m tacticai.interpret")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("shots", help="build the synthetic kick-candidate dataset (run inside the engine Docker image)")
    s.add_argument("--matches", type=int, default=8, help="full matches, seeds 1000..")
    s.add_argument("--situations", type=int, default=40, help="300-step situations, seeds 50000..")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--out", default="data/datasets/shots_v2")
    z = sub.add_parser("analyze", help="write <match_dir>/interpret/ from a match package")
    z.add_argument("match_dir")
    z.add_argument("--xg", default=XG_DEFAULT, help="xG model JSON (ignored if the file does not exist)")
    z.add_argument("--xpass", default=XPASS_DEFAULT, help="xPass model JSON (ignored if the file does not exist)")
    q = sub.add_parser("mcp", help="serve the Stats Tools over stdio (MCP)")
    q.add_argument("--root", default="data/matches")
    t = sub.add_parser("train-xg", help="train the engine xG model on the shot dataset")
    t.add_argument("--data", default="data/datasets/shots_v2")
    t.add_argument("--out", default=XG_DEFAULT)
    u = sub.add_parser("train-xpass", help="train the engine xPass model on the pass dataset")
    u.add_argument("--data", default="data/datasets/v3")
    u.add_argument("--out", default=XPASS_DEFAULT)
    a = ap.parse_args()
    if a.cmd == "analyze":
        return print(analyze(a.match_dir, xg_model=load_xg(a.xg) if os.path.exists(a.xg) else None,
                             xpass_model=load_xg(a.xpass) if os.path.exists(a.xpass) else None))
    if a.cmd == "mcp":
        from .mcp_server import run
        return run(a.root)
    if a.cmd == "train-xg":
        return print(json.dumps(train(a.data, a.out), indent=1))
    if a.cmd == "train-xpass":
        return print(json.dumps(train_xpass(a.data, a.out), indent=1))
    print(json.dumps(build(a.matches, a.situations, a.workers, a.out), indent=2))
