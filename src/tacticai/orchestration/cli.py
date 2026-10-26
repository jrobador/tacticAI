"""python -m tacticai.orchestration: the job (start, run), re-running the later stages on published matches (enrich, refresh)
and the match library (library-plan, library, library-render, library-refresh)."""
import argparse
import os
import shutil
import sys
import tempfile

from ..core.files import write_json
from . import jobs, pipeline
from .library import TEMPLATES, build_library, library_dir, make_plan, read_index, refresh_library

PIPELINE_COMMANDS = ("start", "run", "enrich", "refresh")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] and argv[0] in PIPELINE_COMMANDS:
        return pipeline.main(argv)
    ap = argparse.ArgumentParser(prog="python -m tacticai.orchestration",
                                 epilog="job commands: start [<job_id>] | run <job_id> | enrich <match_id>|--all | refresh <match_id>|--all")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("library-plan", help="write the match library plan (pure Python, no engine)")
    lp.add_argument("--out", default="data/library_plan.json")
    lb = sub.add_parser("library", help="build the library entries of a plan, no video (engine image)")
    lb.add_argument("--plan", default="data/library_plan.json")
    lb.add_argument("--workers", type=int, default=4)
    lb.add_argument("--only", nargs="+", help="build only these entry_ids")
    lr = sub.add_parser("library-render", help="render library entries with video and publish them (engine image + Xvfb)")
    lr.add_argument("entry_ids", nargs="*")
    lr.add_argument("--pick-demo", action="store_true", help="render the 5 demo entries")
    rf = sub.add_parser("library-refresh", help="recompute events, analysis and index stats of the library entries in place")
    rf.add_argument("--entry", nargs="+", help="only these entry_ids")
    a = ap.parse_args(argv)
    if a.cmd == "library-refresh":
        ok, failed, changed = refresh_library(a.entry)
        print(f"summary: {ok} ok, {failed} failed, {changed} changed goals/shots/attacker_xg", flush=True)
        sys.exit(1 if failed else 0)
    if a.cmd == "library-render":
        return run_library_render(a)
    if a.cmd == "library-plan":
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        write_json(a.out, make_plan())
        print(f"done: {a.out}")
        return
    if a.cmd == "library":
        report = build_library(a.plan, a.workers, a.only)
        print(f"done; {len(report)} entries without a result, see build_report.json")
        return


def pick_demo(index):
    """The 5 demo entries: per template the goal with the highest non-null attacker_xg (none: the lowest entry_id), then
    the highest non-null attacker_xg among the rest. Ties: lowest entry_id."""
    entries = sorted(index["entries"], key=lambda e: e["entry_id"])
    picked, missing = [], []
    for template in sorted(TEMPLATES):
        goals = [e for e in entries if e["template"] == template and e["entry_id"].split("-")[2] == "goal"]
        with_xg = [e for e in goals if e["attacker_xg"] is not None]
        if with_xg:
            picked.append(max(with_xg, key=lambda e: e["attacker_xg"]))  # max keeps the first of equals: lowest entry_id
        elif goals:
            picked.append(goals[0])
        else:
            missing.append(f"a goal entry for template {template}")
    rest = [e for e in entries if e not in picked and e["attacker_xg"] is not None]
    if rest:
        picked.append(max(rest, key=lambda e: e["attacker_xg"]))
    else:
        missing.append("a fifth candidate with non-null attacker_xg")
    if missing:
        sys.exit("ERROR: --pick-demo needs the library to have: " + "; ".join(missing))
    return [e["entry_id"] for e in picked]


def run_library_render(a):
    index = read_index(library_dir())
    if a.pick_demo and a.entry_ids:
        sys.exit("ERROR: give entry ids or --pick-demo, not both")
    ids = pick_demo(index) if a.pick_demo else a.entry_ids
    if not ids:
        sys.exit("ERROR: give entry ids or --pick-demo")
    done = {e["entry_id"]: e["match_id"] for e in index["entries"]}
    os.makedirs(jobs.data_dir(), exist_ok=True)
    failed = 0
    for entry_id in ids:
        if done.get(entry_id):
            print(f"{entry_id}: already rendered as {done[entry_id]}")
            continue
        match_id = jobs.new_job_id()
        staging = tempfile.mkdtemp(prefix="library-render-", dir=os.path.abspath(jobs.data_dir()))
        try:
            warnings = pipeline.render_library_entry(entry_id, match_id, staging, lambda state, progress=None: print(f"{entry_id}: {state}", flush=True))
            print(f"{entry_id}: published matches/{match_id}" + (f" ({'; '.join(warnings)})" if warnings else ""))
        except Exception as err:
            failed += 1
            print(f"{entry_id}: FAILED {err}", file=sys.stderr)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    sys.exit(1 if failed else 0)
