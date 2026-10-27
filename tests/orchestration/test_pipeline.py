import io
import hashlib
import json
import os
import sys

import pytest

from tacticai.orchestration import jobs, pipeline
from tacticai.orchestration import library as bl
from tacticai.orchestration.cli import pick_demo

RECIPE = {"mode": "situation", "home": {}, "away": {},
          "situation": {"template": "counter", "ball_owner": "home", "wanted": ["goal_by_team:home"]}, "seeds": 2}


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("TAI_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(pipeline, "load_xg", lambda path: None)
    monkeypatch.setattr(pipeline, "run_agents", lambda match_dir: ["agents not implemented"])
    monkeypatch.setattr(pipeline, "explain_run", lambda d: STEPS.append("explain") or ([], []))
    monkeypatch.setattr(pipeline, "personalize_run", lambda d, **kw: STEPS.append("personalize") or [])
    monkeypatch.setattr(pipeline, "plans_run", lambda d, **kw: STEPS.append("plans") or [])
    monkeypatch.setattr(pipeline, "heatmaps_run", lambda d: STEPS.append("heatmaps") or [])
    monkeypatch.setattr(pipeline, "reels_run", lambda d, video=None: STEPS.append("reels") or ["reel g004 failed: boom"])
    monkeypatch.setattr(pipeline, "rundown_run", lambda d: [])  # the fake matches have no analysis files
    STEPS.clear()


STEPS = []


def fake_match(root, name="recipe_situation_0", tracking="rows"):
    out = os.path.join(root, name)
    os.makedirs(out)
    json.dump({"match_id": name}, open(os.path.join(out, "meta.json"), "w"))
    open(os.path.join(out, "tracking.jsonl"), "w").write(tracking)
    return out


def patch_analyze(monkeypatch, job_id):
    calls = []

    def analyze(match_dir, xg, xpass, vaep=None):
        calls.append(match_dir)
        assert not os.path.exists(jobs.match_dir(job_id)), "published before analyze"
    monkeypatch.setattr(pipeline, "analyze", analyze)
    return calls


def fake_search(results, winner):
    def search(recipe, staging, workers, render_winner, on_progress, on_render, preview_path=None):
        for i in range(len(results)):
            on_progress(i + 1, len(results))
        out = None
        if winner is not None:
            on_render()
            out = fake_match(staging)
            json.dump({"winner": winner}, open(os.path.join(out, "search_report.json"), "w"))
        else:
            os.makedirs(staging, exist_ok=True)
            json.dump({"winner": None}, open(os.path.join(staging, "search_situation_0.json"), "w"))
        return out, {"results": results, "winner": winner}
    return search


def test_start_fails_only_its_own_job(monkeypatch):
    mine, other = jobs.create({"recipe": RECIPE}), jobs.create({"recipe": RECIPE})
    monkeypatch.setattr(pipeline.subprocess, "call", lambda cmd: 3)
    assert pipeline.start(mine) == 3
    s = jobs.read(mine)
    assert (s["state"], s["message"]) == ("failed", "the process exited with code 3")
    assert jobs.read(other)["state"] == "queued"


def test_start_without_queued_job_exits_0():
    assert pipeline.start() == 0


def test_start_keeps_a_terminal_state(monkeypatch):
    job_id = jobs.create({"recipe": RECIPE})
    jobs.write(job_id, state="no_winner", message="x")
    monkeypatch.setattr(pipeline.subprocess, "call", lambda cmd: 2)
    pipeline.start(job_id)
    assert jobs.read(job_id)["state"] == "no_winner"


def test_recipe_job_publishes_after_analyze(monkeypatch):
    job_id = jobs.create({"recipe": RECIPE})
    calls = patch_analyze(monkeypatch, job_id)
    monkeypatch.setattr(pipeline, "search", fake_search([{"seed": 0, "ok": True}, {"seed": 1, "error": "x"}], 0))
    assert pipeline.run(job_id) == 0
    s = jobs.read(job_id)
    assert (s["state"], s["match_id"], s["failed_seeds"]) == ("done", job_id, 1)
    assert s["progress"] is None and len(calls) == 1 and STEPS == ["explain", "personalize", "plans", "heatmaps", "reels"]
    assert s["message"] == "agents not implemented; reel g004 failed: boom"
    assert json.load(open(os.path.join(jobs.match_dir(job_id), "meta.json")))["match_id"] == job_id
    jd = jobs.job_dir(job_id)
    assert os.path.exists(os.path.join(jd, "search_report.json"))
    assert not os.path.exists(os.path.join(jd, "staging", job_id))


def test_agents_exception_still_publishes(monkeypatch):
    job_id = jobs.create({"recipe": RECIPE})
    patch_analyze(monkeypatch, job_id)
    monkeypatch.setattr(pipeline, "search", fake_search([{"seed": 0, "ok": True}], 0))
    monkeypatch.setattr(pipeline, "run_agents", lambda d: 1 / 0)
    pipeline.run(job_id)
    s = jobs.read(job_id)
    assert s["state"] == "done" and "division by zero" in s["message"] and os.path.isdir(jobs.match_dir(job_id))


def test_all_seeds_errored_is_failed(monkeypatch):
    job_id = jobs.create({"recipe": RECIPE})
    monkeypatch.setattr(pipeline, "search", fake_search([{"seed": 0, "error": "boom"}, {"seed": 1, "error": "bam"}], None))
    assert pipeline.run(job_id) == 1
    s = jobs.read(job_id)
    assert s["state"] == "failed" and "boom" in s["message"] and s["failed_seeds"] == 2
    assert os.path.exists(os.path.join(jobs.job_dir(job_id), "search_report.json"))
    assert not os.path.exists(jobs.match_dir(job_id))


def test_no_winner(monkeypatch):
    job_id = jobs.create({"recipe": RECIPE})
    miss = {"ok": False, "missing": ["goal_by_team:home"]}
    monkeypatch.setattr(pipeline, "search", fake_search([{"seed": 0, **miss}, {"seed": 1, **miss}], None))
    assert pipeline.run(job_id) == 2
    s = jobs.read(job_id)
    assert s["state"] == "no_winner" and "missing most often: goal_by_team:home" in s["message"]
    assert os.path.exists(os.path.join(jobs.job_dir(job_id), "search_report.json"))


def library_with_entry(sha):
    lib = bl.library_dir()
    entry_id = "counter-home-goal-01"
    os.makedirs(os.path.join(lib, entry_id))
    recipe = {**bl.make_plan()["recipes"][0]["recipe"], "seed": 7, "seeds": 1}
    json.dump(recipe, open(os.path.join(lib, entry_id, "recipe.json"), "w"))
    bl.update_index(lib, lambda i: i["entries"].append(
        {"entry_id": entry_id, "template": "counter", "tracking_sha256": sha, "match_id": None, "attacker_xg": None}))
    return entry_id


def fake_render(tracking):
    return lambda recipe, seed, staging, render, **kw: (fake_match(staging, "recipe_situation_7", tracking),)


def test_library_job_publishes_and_links(monkeypatch):
    entry_id = library_with_entry(hashlib.sha256(b"rows").hexdigest())
    job_id = jobs.create({"library_id": entry_id})
    patch_analyze(monkeypatch, job_id)
    monkeypatch.setattr(pipeline, "generate_from_recipe", fake_render("rows"))
    assert pipeline.run(job_id) == 0
    assert jobs.read(job_id)["state"] == "done"
    meta = json.load(open(os.path.join(jobs.match_dir(job_id), "meta.json")))
    assert (meta["match_id"], meta["library_id"]) == (job_id, entry_id)
    assert bl.read_index(bl.library_dir())["entries"][0]["match_id"] == job_id


def test_library_hash_mismatch_is_failed(monkeypatch):
    entry_id = library_with_entry(hashlib.sha256(b"rows").hexdigest())
    job_id = jobs.create({"library_id": entry_id})
    calls = patch_analyze(monkeypatch, job_id)
    monkeypatch.setattr(pipeline, "generate_from_recipe", fake_render("other rows"))
    assert pipeline.run(job_id) == 1
    s = jobs.read(job_id)
    assert s["state"] == "failed" and "differs" in s["message"]
    assert not calls and not os.path.exists(jobs.match_dir(job_id))
    assert bl.read_index(bl.library_dir())["entries"][0]["match_id"] is None


def test_pick_demo():
    def e(eid, xg):
        return {"entry_id": eid, "template": eid.split("-")[0], "attacker_xg": xg}
    index = {"entries": [
        e("counter-home-goal-02", 0.3), e("counter-away-goal-01", 0.3), e("counter-home-shot-01", 0.9),
        e("build_up-home-goal-01", None), e("build_up-away-goal-02", None), e("build_up-home-shot-02", 0.5),
        e("wing_attack_left-home-goal-01", 0.1), e("wing_attack_left-home-goal-02", 0.2),
        e("wing_attack_right-home-shot-01", 0.4), e("wing_attack_right-home-goal-03", 0.05)]}
    # templates in alphabetical order. build_up: only null xg -> lowest entry_id; counter: tie at 0.3 -> lowest entry_id;
    # fifth: highest xg among the rest = counter-home-shot-01
    assert pick_demo(index) == ["build_up-away-goal-02", "counter-away-goal-01", "wing_attack_left-home-goal-02",
                                "wing_attack_right-home-goal-03", "counter-home-shot-01"]
    # missing goals and no fifth candidate: one clear error naming them
    index = {"entries": [e("counter-home-goal-01", 0.3)]}
    with pytest.raises(SystemExit) as err:
        pick_demo(index)
    assert "wing_attack_right" in str(err.value) and "fifth candidate" in str(err.value)


def test_failing_render_stops_watchdog_and_kills_ffmpeg(tmp_path, monkeypatch):
    from tacticai.ingest.application import generate_match as gm
    events = []

    class Proc:
        stdin = type("S", (), {"close": lambda self: events.append("stdin")})()
        poll = lambda self: None
        kill = lambda self: events.append("kill")
        wait = lambda self: events.append("wait")

    class Video:
        proc = Proc()
        def __init__(self, *a): pass
        def write(self, b): pass

    class Dog:
        def __init__(self, *a): pass
        def start(self): events.append("start")
        def progress(self, *a): pass
        def stop(self): events.append("dog.stop")

    class Game:
        def step(self):
            raise ValueError("engine blew up")

    monkeypatch.setattr(gm, "VideoWriter", Video)
    monkeypatch.setattr(gm, "RenderWatchdog", Dog)
    with pytest.raises(ValueError, match="engine blew up"):
        gm._simulate(Game(), str(tmp_path), 0, 10, True, 60, 100)
    assert "dog.stop" in events and "kill" in events and "wait" in events


def test_explain_failure_fails_the_job_without_publishing(monkeypatch):
    job_id = jobs.create({"recipe": RECIPE})
    patch_analyze(monkeypatch, job_id)
    monkeypatch.setattr(pipeline, "search", fake_search([{"seed": 0, "ok": True}], 0))
    monkeypatch.setattr(pipeline, "explain_run", lambda d: 1 / 0)
    assert pipeline.run(job_id) == 1
    s = jobs.read(job_id)
    assert s["state"] == "failed" and "division by zero" in s["message"] and not os.path.exists(jobs.match_dir(job_id))


def test_steps_report_their_state_and_progress(monkeypatch):
    seen = []
    monkeypatch.setattr(pipeline, "analyze", lambda *a: None)
    pipeline.analyze_and_publish(fake_match(str(jobs.job_dir("x")), "m"), "20261024-000000-aaaa", lambda s, p=None: seen.append((s, p)))
    assert [s for s, _ in seen[:2]] == ["analyzing", "agents"] and seen[0][1] is None and seen[1][1] is None
    steps = {}
    for state, progress in seen[2:]:
        steps.setdefault(state, []).append(progress)
    assert list(steps) == ["explaining", "personalizing", "directing", "rendering_assets"]
    assert all(p[0]["done"] == 0 and p[-1]["done"] == p[-1]["total"] == p[0]["total"] for p in steps.values())


def test_enrich_creates_the_three_folders_and_replaces_old_ones(monkeypatch):
    import shutil
    from pathlib import Path
    fix = Path(__file__).parent.parent / "explain" / "fixtures" / "match"
    match_id = "20261024-000000-aaaa"
    dest = jobs.match_dir(match_id)
    shutil.copytree(fix, dest)
    open(os.path.join(dest, "tracking.jsonl"), "w").write("")
    os.makedirs(os.path.join(dest, "explain"))
    open(os.path.join(dest, "explain", "stale.txt"), "w").write("old")
    from tacticai.explain.application import build_insights as B
    from tacticai.personalize.application import build_personalize
    from tacticai.render.application import plans
    monkeypatch.setattr(pipeline, "explain_run", lambda d: B.run(d, context={}))
    monkeypatch.setattr(pipeline, "personalize_run", lambda d, **kw: build_personalize.run(d, context={}))
    monkeypatch.setattr(pipeline, "plans_run", lambda d, **kw: plans.run(d, context={}))
    pipeline.enrich(match_id)
    assert os.path.isfile(os.path.join(dest, "explain", "insights.jsonl")) and not os.path.exists(os.path.join(dest, "explain", "stale.txt"))
    assert len(os.listdir(os.path.join(dest, "personalize", "variants"))) == 18 and len(os.listdir(os.path.join(dest, "personalize", "recaps"))) == 18
    assert len(os.listdir(os.path.join(dest, "render", "plans"))) == 12
    assert sorted(n for n in os.listdir(dest) if n.startswith(".")) == []
    with pytest.raises(RuntimeError):
        pipeline.enrich("20261024-000000-bbbb")


def test_enrich_gives_the_reels_step_the_published_video(monkeypatch):
    import shutil
    from pathlib import Path
    match_id = "20261024-000000-aaaa"
    shutil.copytree(Path(__file__).parent.parent / "explain" / "fixtures" / "match", jobs.match_dir(match_id))
    got = []
    monkeypatch.setattr(pipeline, "reels_run", lambda d, video=None: got.append(video) or [])
    pipeline.enrich(match_id)
    assert got == [os.path.join(jobs.match_dir(match_id), "video.mp4")]


def test_refresh_recomputes_in_a_temp_folder_then_swaps_and_enriches(monkeypatch):
    import shutil
    from pathlib import Path
    match_id = "20261024-000000-aaaa"
    dest = jobs.match_dir(match_id)
    shutil.copytree(Path(__file__).parent.parent / "explain" / "fixtures" / "match", dest)
    open(os.path.join(dest, "events.jsonl"), "w").write("old")
    os.makedirs(os.path.join(dest, "interpret"), exist_ok=True)
    open(os.path.join(dest, "interpret", "stale.txt"), "w").write("old")

    def fake_refresh(d):
        STEPS.append("refresh")
        assert d != dest and open(os.path.join(dest, "events.jsonl")).read() == "old"  # work happens aside
        assert not os.path.exists(os.path.join(d, "events.jsonl"))
        open(os.path.join(d, "events.jsonl"), "w").write("new")
        open(os.path.join(d, "events_summary.json"), "w").write("{}")
        os.makedirs(os.path.join(d, "interpret"))
        open(os.path.join(d, "interpret", "fresh.txt"), "w").write("new")
    monkeypatch.setattr(pipeline, "refresh_match_files", fake_refresh)
    pipeline.refresh(match_id)
    assert STEPS == ["refresh", "explain", "personalize", "plans", "heatmaps", "reels"]
    assert open(os.path.join(dest, "events.jsonl")).read() == "new"
    assert os.listdir(os.path.join(dest, "interpret")) == ["fresh.txt"]
    assert [n for n in os.listdir(dest) if n.startswith(".")] == []
    with pytest.raises(RuntimeError):
        pipeline.refresh("20261024-000000-bbbb")


def test_refresh_all_survives_non_cp1252_warning(monkeypatch):
    monkeypatch.setattr(pipeline, "refresh", lambda m: ["non‑breaking"])
    monkeypatch.setattr(pipeline, "_matches", lambda: ["20261024-000000-aaaa"])
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    assert pipeline.main(["refresh", "--all"]) == 0
    out.seek(0)
    assert "‑" in out.read()
