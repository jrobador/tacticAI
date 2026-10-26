"""Match library: the plan, the single index.json writer and the entry builder."""
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import uuid

from ..interpret.application.analyze_match import analyze
from ..interpret.application.models import load_vaep, load_xg
from ..ingest.domain.recipe import from_dict, to_dict
from ..core.files import read_json, read_jsonl, write_json
from ..ingest.application.generate_match import generate_from_recipe
from ..ingest.application.infer_events import infer_events
from ..ingest.application.search import search

TEMPLATES = ("counter", "wing_attack_right", "wing_attack_left", "build_up")
# (attacking formation, style), (defending formation, style)
COMBOS = (
    (("4-3-3", "counter"), ("4-4-2", "balanced")),
    (("4-3-3", "high_press"), ("4-2-3-1", "balanced")),
    (("4-2-3-1", "counter"), ("5-3-2", "balanced")),
    (("3-4-3", "high_press"), ("4-1-4-1", "possession")),
    (("4-4-2", "possession"), ("3-5-2", "high_press")),
    (("3-5-2", "counter"), ("5-4-1", "counter")),
)
TITLES = {"counter": "counter-attack", "wing_attack_right": "attack down the right",
          "wing_attack_left": "attack down the left", "build_up": "build-up"}
MODELS = os.path.join(os.path.dirname(__file__), "..", "interpret", "models")


def _entry(template, side, kind, nn, combo, seed=0):
    team = lambda fs: {"formation": fs[0], "style": fs[1], "level": 1.0}
    recipe = {"mode": "situation", "home": team(combo[0] if side == "home" else combo[1]),
              "away": team(combo[0] if side == "away" else combo[1]),
              "situation": {"template": template, "ball_owner": side, "ends_when": "steps",
                            "wanted": [f"{kind}_by_team:{side}"]},
              "seeds": 200 if kind == "goal" else 50, "steps": 300, "seed": seed}
    from_dict(recipe)  # validates
    return {"entry_id": f"{template}-{side}-{kind}-{nn:02d}", "recipe": recipe}


def make_plan():
    """104 recipes: 4 templates x 2 sides x goal|shot x 6 combos, plus 8 extra build_up goal recipes (seed 1000)."""
    recipes = [_entry(t, s, k, n, c) for t in TEMPLATES for s in ("home", "away") for k in ("goal", "shot")
               for n, c in enumerate(COMBOS, 1)]
    recipes += [_entry("build_up", s, "goal", 7 + i, COMBOS[i], seed=1000) for s in ("home", "away") for i in range(4)]
    return {"plan_version": 1, "recipes": recipes}


def library_dir():
    root = os.environ.get("TAI_OUTPUT_DIR") or os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
    return os.path.abspath(os.path.join(root, "library"))


def _git_head():
    """Recorded only (resume never checks it): TAI_CODE_VERSION, else git rev-parse, else None."""
    if os.environ.get("TAI_CODE_VERSION"):
        return os.environ["TAI_CODE_VERSION"]
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                              cwd=os.path.dirname(__file__)).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def read_index(lib):
    path = os.path.join(lib, "index.json")
    if os.path.exists(path):
        return read_json(path)
    return {"library_version": 1, "code_version": _git_head(), "engine_image": os.environ.get("TAI_ENGINE_IMAGE"),
            "entries": []}


def update_index(lib, fn):
    """The only writer of index.json: read, fn(index) mutates it, write a temp file, os.replace."""
    os.makedirs(lib, exist_ok=True)
    lock = os.path.join(lib, "index.lock")
    deadline = time.monotonic() + 10
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise RuntimeError(f"{lock} is held for over 10 s; if no other process is writing the index, delete it")
            time.sleep(0.05)
    try:
        index = read_index(lib)
        fn(index)
        tmp = os.path.join(lib, f"index.{uuid.uuid4().hex}.tmp")
        write_json(tmp, index)
        os.replace(tmp, os.path.join(lib, "index.json"))
    finally:
        os.remove(lock)
    return index


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _title(r, meta):
    s = r.situation
    what = "goal" if s.wanted[0].startswith("goal") else "shot"
    name = meta["teams"][s.ball_owner]["name"]
    return f"{name} {TITLES[s.template]} ends in a {name} {what}"


def _attacker_xg(enriched, side):
    xgs = [e.get("xg") for e in enriched if e["type"] == "shot" and e["team"] == side]
    return None if any(x is None for x in xgs) else round(sum(xgs), 4)


def _analyze(match_dir):
    """analyze with xG, xPass and VAEP (VAEP only when its model file exists)."""
    vaep = os.path.join(MODELS, "vaep_v1.json")
    analyze(match_dir, load_xg(os.path.join(MODELS, "xg_v1.json")), load_xg(os.path.join(MODELS, "xpass_v1.json")),
            load_vaep(vaep) if os.path.exists(vaep) else None)


def refresh_match_files(match_dir):
    """Recomputes events.jsonl (+ summary) from tracking.jsonl, then interpret/ (what `ingest events` + analyze do)."""
    infer_events(match_dir)
    _analyze(match_dir)


def _stats(match_dir, side):
    """The index fields derived from events/analysis: duration_s, goals, shots, attacker_xg."""
    events, rows = read_jsonl(os.path.join(match_dir, "events.jsonl")), read_jsonl(os.path.join(match_dir, "tracking.jsonl"))
    enriched = read_jsonl(os.path.join(match_dir, "interpret", "events_enriched.jsonl"))
    video = read_json(os.path.join(match_dir, "meta.json")).get("video") or {}
    if video.get("frames") and video.get("fps"):
        duration = round(video["frames"] / video["fps"], 1)
    else:
        duration = round(rows[-1]["t_s"] - rows[0]["t_s"], 1) if rows else 0.0
    return {"duration_s": duration, "goals": sum(e["type"] == "goal" for e in events),
            "shots": sum(e["type"] == "shot" for e in events), "attacker_xg": _attacker_xg(enriched, side)}


def refresh_library(only=None, log=print):
    """Re-derives events, analysis and the index stats of every library entry in place (tracking does not change).
    Returns (ok, failed, changed): entry counts; changed = ok entries whose goals, shots or attacker_xg moved."""
    lib = library_dir()
    index = {e["entry_id"]: e for e in read_index(lib)["entries"]}
    ok = failed = changed = 0
    for d in sorted(os.listdir(lib)):
        path = os.path.join(lib, d)
        if d not in index or not os.path.isdir(path) or d.startswith(("_failed-", "tmp")) or (only and d not in only):
            continue
        try:
            refresh_match_files(path)
            new = _stats(path, index[d]["ball_owner"])
            old = {k: index[d].get(k) for k in new}
            update_index(lib, lambda idx, d=d, new=new: next(e for e in idx["entries"] if e["entry_id"] == d).update(new))
            ok += 1
            diff = {k: (old[k], v) for k, v in new.items() if k != "duration_s" and old[k] != v}
            changed += bool(diff)
            log(f"{d}: ok" + (f" changed {diff}" if diff else ""))
        except Exception as err:
            failed += 1
            log(f"{d}: FAILED {type(err).__name__}: {err}")
    return ok, failed, changed


def _rename(src, dst):
    """os.rename, retried 5 times 1 s apart on PermissionError only (Windows bind mounts refuse it now and then)."""
    for attempt in range(5):
        try:
            return os.rename(src, dst)
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(1)


def build_entry(entry_id, recipe_dict, lib, workers=4):
    """Builds library/<entry_id>/ and returns (index entry, None), or (None, reason) when it has no winner or fails."""
    r = from_dict(recipe_dict)
    tmp, keep = tempfile.mkdtemp(dir=lib), False
    try:
        _, report = search(r, out_root=tmp, workers=workers, render_winner=False)
        winner = report["winner"]
        if winner is None:
            return None, "no winner"
        expected = next(x for x in report["results"] if x["seed"] == winner)["tracking_sha256"]
        out = generate_from_recipe(r, winner, tmp, render=False)[0]
        if _sha256(os.path.join(out, "tracking.jsonl")) != expected:
            return None, f"tracking hash differs from the search run (seed {winner})"
        norm = {**to_dict(r), "seed": winner, "seeds": 1}
        write_json(os.path.join(out, "recipe.json"), norm)
        _analyze(out)
        side = r.situation.ball_owner
        meta = read_json(os.path.join(out, "meta.json"))
        entry = {"entry_id": entry_id, "title": _title(r, meta), "template": r.situation.template, "ball_owner": side,
                 "wanted": list(r.situation.wanted), "home": norm["home"], "away": norm["away"],
                 "seed": winner, "tracking_sha256": expected, **_stats(out, side), "match_id": None}
        dest = os.path.join(lib, entry_id)
        if os.path.exists(dest):
            shutil.rmtree(dest)  # leftover of a run that died before the index update
        try:
            _rename(out, dest)
        except PermissionError as err:  # keep the built work: a person moves it into place
            kept = os.path.join(lib, "_failed-" + entry_id)
            if os.path.exists(kept):
                shutil.rmtree(kept, ignore_errors=True)
            keep = True
            try:
                os.rename(tmp, kept)
                kept = os.path.join(kept, os.path.basename(out))
            except OSError:
                kept = out
            return None, f"PermissionError renaming to {dest}: {err}; built folder kept at {kept}, move it to {dest} by hand"
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    return entry, None


def build_library(plan_path, workers=4, only=None):
    """Builds every plan entry missing from the index (sequentially: each search already uses `workers`)."""
    lib = library_dir()
    os.makedirs(lib, exist_ok=True)
    for d in os.listdir(lib):  # stray temp folders of runs that died (this run has created none yet)
        p = os.path.join(lib, d)
        if d.startswith("tmp") and os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    plan = read_json(plan_path)["recipes"]
    done = {e["entry_id"] for e in read_index(lib)["entries"]}
    report_path = os.path.join(lib, "build_report.json")
    report = read_json(report_path) if os.path.exists(report_path) else {}
    for item in plan:
        eid = item["entry_id"]
        if eid in done or (only and eid not in only):
            continue
        try:
            entry, why = build_entry(eid, item["recipe"], lib, workers)
        except Exception as err:  # keep going; the report says what failed
            entry, why = None, f"{type(err).__name__}: {err}"
        if entry:
            update_index(lib, lambda idx, e=entry: idx["entries"].append(e))
            report.pop(eid, None)
        else:
            report[eid] = why
        write_json(report_path, report)
        print(f"{eid}: {'ok' if entry else why}", flush=True)
    return report
