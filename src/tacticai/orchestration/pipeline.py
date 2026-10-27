"""The job: `start [job_id]` supervises `run <job_id>` as a child process."""
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from . import jobs
from .jobs import start  # noqa: F401  (python -m tacticai.orchestration start)
from .library import MODELS, library_dir, read_index, refresh_match_files, update_index
from ..ingest.application.generate_match import generate_from_recipe
from ..ingest.application.search import search
from ..ingest.domain.recipe import from_dict
from ..explain.application.build_insights import run as explain_run
from ..explain.application.build_insights import build_match_context
from ..core.files import read_json, read_jsonl, write_json
from ..interpret.application.agents import run_agents
from ..interpret.application.analyze_match import analyze
from ..interpret.application.models import load_vaep, load_xg
from ..personalize.application import lens_agent, recap_agent, recaps
from ..personalize.application.build_personalize import run as personalize_run
from ..render.application.reels import run as reels_run
from ..render.application.heatmaps import run as heatmaps_run
from ..render.application.rundown import run as rundown_run
from ..render.application.thumb import run as thumb_run
from ..render.application import director_agent
from ..render.application.plans import director_inputs, run as plans_run

ENRICH_DIRS = ("explain", "personalize", "render")


def _set_meta(match_dir, **fields):
    path = os.path.join(match_dir, "meta.json")
    write_json(path, {**read_json(path), **fields})


def _replay(future):
    """An agent replacement that returns the finished call's result or re-raises its exception, so every fallback stays as is."""
    return lambda *args: future.result()


def _start_agents(pool, match_dir):
    """Lens, Recap and Director are independent: start them together. Returns the kwargs for personalize_run and plans_run;
    {} when the inputs cannot be built (those steps then build them and fail or warn as they always did)."""
    try:
        insights = read_jsonl(os.path.join(match_dir, "explain", "insights.jsonl"))
        ctx = build_match_context(match_dir)
        picked = recaps.picks(insights)
        _, info = director_inputs(insights)
    except Exception:
        return {}, {}
    lens = pool.submit(lens_agent.adapt_texts, insights, ctx)
    recap = pool.submit(recap_agent.write_recaps, insights, picked, ctx) if picked else None
    director = pool.submit(director_agent.plan_all, insights, info, ctx)
    return ({"lens_agent": _replay(lens), "context": ctx, **({"recap_agent": _replay(recap)} if recap else {})},
            {"agent": _replay(director), "context": ctx})


def enrich_steps(match_dir, set_state, video=None):
    """explaining -> personalizing -> directing -> rendering_assets on a match folder. Deterministic: an exception propagates, except
    reel failures (they go to render/reels/manifest.json and the warnings). set_state(state, progress=None); each step ends with done == total.
    video: path of video.mp4 when it is not inside match_dir. Returns the warnings (LLM fallbacks, reel failures)."""
    set_state("explaining", {"done": 0, "total": 1})
    warnings = list(explain_run(match_dir)[1])
    set_state("explaining", {"done": 1, "total": 1})
    with ThreadPoolExecutor(max_workers=3) as pool:
        personalize_kw, plans_kw = _start_agents(pool, match_dir)  # the Director's answer is ready (or not) by the time `directing` runs
        set_state("personalizing", {"done": 0, "total": 36})  # 18 variants + 18 recaps
        warnings += personalize_run(match_dir, **personalize_kw)
        set_state("personalizing", {"done": 36, "total": 36})
        set_state("directing", {"done": 0, "total": 12})
        warnings += plans_run(match_dir, **plans_kw)
        set_state("directing", {"done": 12, "total": 12})
    set_state("rendering_assets", {"done": 0, "total": 2})  # heatmaps, reels
    heatmaps_run(match_dir)
    set_state("rendering_assets", {"done": 1, "total": 2})
    warnings += thumb_run(match_dir, video)
    warnings += rundown_run(match_dir)
    warnings += reels_run(match_dir, video)  # after the rundown: the reels are its goals and shots
    set_state("rendering_assets", {"done": 2, "total": 2})
    return warnings


def analyze_and_publish(staging_match, match_id, set_state):
    """Common steps: analyze -> agents -> explaining -> personalizing -> directing -> rendering_assets -> publish with os.rename.
    set_state(state, progress=None) reports progress. Returns the warnings."""
    set_state("analyzing", None)
    vaep = os.path.join(MODELS, "vaep_v1.json")
    analyze(staging_match, load_xg(os.path.join(MODELS, "xg_v1.json")), load_xg(os.path.join(MODELS, "xpass_v1.json")),
            load_vaep(vaep) if os.path.exists(vaep) else None)
    set_state("agents", None)
    try:
        warnings = list(run_agents(staging_match))
    except Exception as err:  # the match is published without agents.json
        warnings = [f"agents failed: {err}"]
    warnings += enrich_steps(staging_match, set_state)
    dest = os.path.join(os.path.abspath(jobs.data_dir()), "matches", match_id)
    if os.path.exists(dest):
        raise RuntimeError(f"match {match_id} already exists")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    os.rename(staging_match, dest)
    return warnings


def render_library_entry(entry_id, match_id, staging, set_state, preview_path=None):
    """Library job, shared with `orchestration library-render`: render the entry's saved recipe and seed, check the tracking
    hash against the index, analyze, agents, publish and set match_id in the index. Returns the warnings."""
    lib = library_dir()
    entry = next((e for e in read_index(lib)["entries"] if e["entry_id"] == entry_id), None)
    if entry is None:
        raise RuntimeError(f"unknown library entry {entry_id}")
    recipe = read_json(os.path.join(lib, entry_id, "recipe.json"))
    set_state("rendering", None)
    out = generate_from_recipe(from_dict(recipe), recipe["seed"], staging, render=True, preview_path=preview_path)[0]
    with open(os.path.join(out, "tracking.jsonl"), "rb") as f:
        got = hashlib.sha256(f.read()).hexdigest()
    if got != entry["tracking_sha256"]:
        raise RuntimeError(f"rendered tracking differs from the library entry {entry_id} (seed {recipe['seed']})")
    match_dir = os.path.join(staging, match_id)
    os.rename(out, match_dir)
    _set_meta(match_dir, match_id=match_id, library_id=entry_id)
    warnings = analyze_and_publish(match_dir, match_id, set_state)

    def link(index):
        for e in index["entries"]:
            if e["entry_id"] == entry_id:
                e["match_id"] = match_id
    update_index(lib, link)
    return warnings


def _no_winner_message(recipe, results):
    met = sum("error" not in x and x["ok"] for x in results)
    wanted = recipe.situation.wanted if recipe.situation else []
    miss = Counter(m for x in results for m in x.get("missing", []))
    return (f"tried {len(results)} seeds, {met} met {wanted or 'nothing in particular'}, no winner; "
            f"missing most often: {miss.most_common(1)[0][0] if miss else 'n/a'}")


def _job_state(job_id):
    return lambda state, progress=None: jobs.write(job_id, state=state, progress=progress)


def _run_recipe(job_id, request):
    recipe = from_dict(request["recipe"])
    staging = os.path.join(jobs.job_dir(job_id), "staging")
    jobs.write(job_id, state="searching", progress={"done": 0, "total": recipe.seeds})
    out, report = search(
        recipe, staging, workers=int(os.environ.get("TAI_WORKERS", "4")), render_winner=True,
        on_progress=lambda done, total: jobs.write(job_id, progress={"done": done, "total": total}),
        on_render=lambda: jobs.write(job_id, state="rendering"),
        preview_path=os.path.join(jobs.job_dir(job_id), "preview.jpg"))
    found = [os.path.join(out, "search_report.json")] if out else glob.glob(os.path.join(staging, "search_*.json"))
    if found:
        shutil.move(found[0], os.path.join(jobs.job_dir(job_id), "search_report.json"))
    results = report["results"]
    errors = [x for x in results if "error" in x]
    jobs.write(job_id, failed_seeds=len(errors), search={
        "seeds": len(results), "met": sum("error" not in x and x["ok"] for x in results), "seed": report["winner"]})
    if errors and len(errors) == len(results):
        jobs.write(job_id, state="failed", message=f"all seeds failed; first error: {errors[0]['error']}")
        return 1
    if report["winner"] is None:
        jobs.write(job_id, state="no_winner", message=_no_winner_message(recipe, results))
        return 2
    match_dir = os.path.join(staging, job_id)
    os.rename(out, match_dir)
    _set_meta(match_dir, match_id=job_id)
    warnings = analyze_and_publish(match_dir, job_id, _job_state(job_id))
    jobs.write(job_id, state="done", match_id=job_id, message="; ".join(warnings) or None, progress=None)
    return 0


def _run_library(job_id, request):
    staging = os.path.join(jobs.job_dir(job_id), "staging")
    warnings = render_library_entry(request["library_id"], job_id, staging, _job_state(job_id),
                                   os.path.join(jobs.job_dir(job_id), "preview.jpg"))
    jobs.write(job_id, state="done", match_id=job_id, message="; ".join(warnings) or None, progress=None)
    return 0


def _mirror(match_dir, tmp, skip=()):
    """A light copy of the match for the enrichment steps: hard links (or copies) of the inputs, no video, no output folders."""
    os.makedirs(tmp)
    for name in os.listdir(match_dir):
        src = os.path.join(match_dir, name)
        if name == "video.mp4" or name in ENRICH_DIRS or name in skip or name.startswith("."):
            continue
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(tmp, name))
        else:
            try:
                os.link(src, os.path.join(tmp, name))
            except OSError:
                shutil.copy2(src, os.path.join(tmp, name))


def enrich(match_id):
    """Migration: explaining -> directing on a published match, no engine. Each new folder is built in a temp folder inside the
    match and swapped in at the end (old one renamed aside, then deleted). Returns the warnings."""
    match_dir = os.path.join(os.path.abspath(jobs.data_dir()), "matches", match_id)
    if not jobs.JOB_ID_RE.match(match_id) or not os.path.isfile(os.path.join(match_dir, "meta.json")):
        raise RuntimeError(f"unknown match {match_id}")
    tmp = os.path.join(match_dir, f".enrich-{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        _mirror(match_dir, tmp)
        warnings = enrich_steps(tmp, lambda state, progress=None: print(f"{match_id}: {state}", flush=True), os.path.join(match_dir, "video.mp4"))
        for name in ENRICH_DIRS:
            new, dest, old = os.path.join(tmp, name), os.path.join(match_dir, name), os.path.join(match_dir, f".{name}.old-{os.getpid()}")
            if not os.path.isdir(new):
                continue
            if os.path.exists(dest):
                os.rename(dest, old)
            os.rename(new, dest)
            shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return warnings


def _swap(new, dest, old):
    if os.path.exists(dest):
        os.rename(dest, old)
    os.rename(new, dest)
    shutil.rmtree(old, ignore_errors=True)


def refresh(match_id):
    """Recomputes events and interpret/ of a published match from its tracking (built in a temp folder; each events file is
    os.replace'd, interpret/ is swapped as a whole), runs the agents on the recomputed interpret/, then enrich. Returns the agents and enrich warnings."""
    match_dir = os.path.join(os.path.abspath(jobs.data_dir()), "matches", match_id)
    if not jobs.JOB_ID_RE.match(match_id) or not os.path.isfile(os.path.join(match_dir, "meta.json")):
        raise RuntimeError(f"unknown match {match_id}")
    tmp = os.path.join(match_dir, f".refresh-{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        _mirror(match_dir, tmp, skip=("events.jsonl", "events_summary.json", "interpret"))
        refresh_match_files(tmp)
        warnings = list(run_agents(tmp))  # on the recomputed interpret/, before the swap
        for name in ("events.jsonl", "events_summary.json"):
            os.replace(os.path.join(tmp, name), os.path.join(match_dir, name))
        _swap(os.path.join(tmp, "interpret"), os.path.join(match_dir, "interpret"), os.path.join(match_dir, f".interpret.old-{os.getpid()}"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return warnings + enrich(match_id)


def _matches():
    root = os.path.join(os.path.abspath(jobs.data_dir()), "matches")
    return [m for m in sorted(os.listdir(root)) if jobs.JOB_ID_RE.match(m)] if os.path.isdir(root) else []


def refresh_all():
    failed = 0
    for match_id in _matches():
        try:
            warnings = refresh(match_id)
            print(f"{match_id}: refreshed" + (f" ({'; '.join(warnings)})" if warnings else ""), flush=True)
        except Exception as err:
            failed += 1
            print(f"{match_id}: FAILED {err}", file=sys.stderr)
    return 1 if failed else 0


def enrich_all():
    root = os.path.join(os.path.abspath(jobs.data_dir()), "matches")
    failed = 0
    for match_id in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if not jobs.JOB_ID_RE.match(match_id):
            continue
        try:
            warnings = enrich(match_id)
            print(f"{match_id}: enriched" + (f" ({'; '.join(warnings)})" if warnings else ""), flush=True)
        except Exception as err:
            failed += 1
            print(f"{match_id}: FAILED {err}", file=sys.stderr)
    return 1 if failed else 0


def run(job_id):
    """Exit code: 0 done, 1 failed, 2 no_winner."""
    try:
        request = read_json(os.path.join(jobs.job_dir(job_id), "request.json"))
        return (_run_library if "library_id" in request else _run_recipe)(job_id, request)
    except Exception as err:
        traceback.print_exc()
        jobs.write(job_id, state="failed", message=str(err))
        return 1


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["start"] and len(argv) <= 2:
        return start(*argv[1:])
    if argv[:1] == ["run"] and len(argv) == 2:
        return run(argv[1])
    if argv[:1] == ["enrich"] and len(argv) == 2:
        if argv[1] == "--all":
            return enrich_all()
        try:
            print("; ".join(enrich(argv[1])) or "enriched")
            return 0
        except Exception as err:
            sys.exit(f"ERROR: {err}")
    if argv[:1] == ["refresh"] and len(argv) == 2:
        if argv[1] == "--all":
            return refresh_all()
        try:
            print("; ".join(refresh(argv[1])) or "refreshed")
            return 0
        except Exception as err:
            sys.exit(f"ERROR: {err}")
    sys.exit("usage: python -m tacticai.orchestration start [<job_id>] | run <job_id> | enrich <match_id> | enrich --all | refresh <match_id> | refresh --all")


if __name__ == "__main__":
    sys.exit(main())
