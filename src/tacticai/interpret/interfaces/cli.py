import argparse
import os

from ..application.analyze_match import analyze
from ..application.models import load_vaep, load_xg

XG_DEFAULT = "src/tacticai/interpret/models/xg_v1.json"
XPASS_DEFAULT = "src/tacticai/interpret/models/xpass_v1.json"
VAEP_DEFAULT = "src/tacticai/interpret/models/vaep_v1.json"


def main():
    ap = argparse.ArgumentParser(prog="python -m tacticai.interpret")
    sub = ap.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("analyze", help="write <match_dir>/interpret/ from a match package")
    z.add_argument("match_dir")
    z.add_argument("--xg", default=XG_DEFAULT, help="xG model JSON (ignored if the file does not exist)")
    z.add_argument("--xpass", default=XPASS_DEFAULT, help="xPass model JSON (ignored if the file does not exist)")
    z.add_argument("--vaep", default=VAEP_DEFAULT, help="VAEP model JSON (ignored if the file does not exist; without it the rating is null)")
    q = sub.add_parser("mcp", help="serve the Stats Tools over stdio (MCP)")
    q.add_argument("--root", default="data/matches")
    a = ap.parse_args()
    if a.cmd == "analyze":
        return print(analyze(a.match_dir, xg_model=load_xg(a.xg) if os.path.exists(a.xg) else None,
                             xpass_model=load_xg(a.xpass) if os.path.exists(a.xpass) else None,
                             vaep_model=load_vaep(a.vaep) if os.path.exists(a.vaep) else None))
    if a.cmd == "mcp":
        from .mcp_server import run
        return run(a.root)
