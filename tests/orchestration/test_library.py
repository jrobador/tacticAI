import json
import os
import re

import pytest

from tacticai.orchestration import library as bl
from tacticai.ingest.domain.recipe import from_dict

ID = re.compile(r"^[a-z_]+-(home|away)-(goal|shot)-\d{2}$")


def test_plan():
    recipes = bl.make_plan()["recipes"]
    ids = [r["entry_id"] for r in recipes]
    assert len(recipes) == 104 and len(set(ids)) == 104 and all(ID.match(i) for i in ids)
    for r in recipes:
        rec = from_dict(r["recipe"])
        side = rec.situation.ball_owner
        kind = "goal" if "-goal-" in r["entry_id"] else "shot"
        assert r["entry_id"].split("-")[1] == side
        assert rec.situation.wanted == [f"{kind}_by_team:{side}"]
        assert rec.seeds == (200 if kind == "goal" else 50) and rec.steps == 300
    c1 = {r["entry_id"]: r["recipe"] for r in recipes}
    home, away = c1["counter-home-goal-01"], c1["counter-away-goal-01"]
    assert (home["home"]["formation"], home["home"]["style"], home["away"]["formation"]) == ("4-3-3", "counter", "4-4-2")
    assert (away["away"]["formation"], away["away"]["style"], away["home"]["formation"]) == ("4-3-3", "counter", "4-4-2")
    extras = [r for r in recipes if r["recipe"]["seed"] == 1000]
    assert sorted(r["entry_id"] for r in extras) == sorted(
        f"build_up-{s}-goal-{n:02d}" for s in ("home", "away") for n in range(7, 11))


def test_index_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("TAI_ENGINE_IMAGE", "img1")
    lib = str(tmp_path / "library")
    bl.update_index(lib, lambda i: i["entries"].append({"entry_id": "a"}))
    idx = bl.update_index(lib, lambda i: i["entries"].append({"entry_id": "b"}))
    on_disk = json.load(open(os.path.join(lib, "index.json")))
    assert on_disk == idx and [e["entry_id"] for e in on_disk["entries"]] == ["a", "b"]
    assert on_disk["library_version"] == 1 and on_disk["engine_image"] == "img1"
    assert os.listdir(lib) == ["index.json"]  # temp file replaced, not left behind


def _fake(monkeypatch, winner, sha="h", generated_sha="h"):
    def fake_search(r, out_root, workers, render_winner):
        return None, {"winner": winner, "results": [{"seed": winner, "tracking_sha256": sha}]}

    def fake_generate(r, seed, out_root, render):
        out = os.path.join(out_root, f"recipe_situation_{seed}")
        os.makedirs(out)
        with open(os.path.join(out, "tracking.jsonl"), "w") as f:
            f.write(generated_sha)
        with open(os.path.join(out, "meta.json"), "w") as f:
            json.dump({"teams": {"home": {"name": "Wexmoor City"}, "away": {"name": "Brackenford Athletic"}}}, f)
        with open(os.path.join(out, "events.jsonl"), "w") as f:
            f.write(json.dumps({"type": "goal", "team": "home"}) + "\n")
            f.write(json.dumps({"type": "shot", "team": "home"}) + "\n")
            f.write(json.dumps({"type": "shot", "team": "away"}) + "\n")
        return (out,)

    def fake_analyze(out, xg, xpass, vaep=None):
        os.makedirs(os.path.join(out, "interpret"))
        with open(os.path.join(out, "interpret", "events_enriched.jsonl"), "w") as f:
            f.write(json.dumps({"type": "shot", "team": "home", "xg": 0.25}) + "\n")
            f.write(json.dumps({"type": "shot", "team": "home", "xg": 0.5}) + "\n")

    monkeypatch.setattr(bl, "search", fake_search)
    monkeypatch.setattr(bl, "generate_from_recipe", fake_generate)
    monkeypatch.setattr(bl, "analyze", fake_analyze)
    monkeypatch.setattr(bl, "load_xg", lambda p: None)
    monkeypatch.setattr(bl, "_sha256", lambda p: open(p).read())
    monkeypatch.setattr(bl, "read_jsonl", lambda p: [json.loads(l) for l in open(p) if l.strip()]
                        if not p.endswith("tracking.jsonl") else [{"t_s": 1.0, "clock_s": 99.0}, {"t_s": 4.5, "clock_s": 999.0}])


@pytest.fixture
def recipe():
    return bl.make_plan()["recipes"][0]  # counter-home-goal-01


def test_build_accepts_winner_zero(tmp_path, monkeypatch, recipe):
    _fake(monkeypatch, 0)
    entry, why = bl.build_entry(recipe["entry_id"], recipe["recipe"], str(tmp_path))
    assert why is None and entry["seed"] == 0 and entry["goals"] == 1 and entry["shots"] == 2
    assert entry["attacker_xg"] == 0.75 and entry["duration_s"] == 3.5 and entry["title"] == "Wexmoor City counter-attack ends in a Wexmoor City goal" and entry["match_id"] is None
    assert os.path.isdir(tmp_path / recipe["entry_id"]) and os.listdir(tmp_path) == [recipe["entry_id"]]
    saved = json.load(open(tmp_path / recipe["entry_id"] / "recipe.json"))
    assert saved["seed"] == 0 and saved["seeds"] == 1 and saved["steps"] == 300


def test_build_no_winner_goes_to_report(tmp_path, monkeypatch, recipe):
    _fake(monkeypatch, None)
    monkeypatch.setenv("TAI_OUTPUT_DIR", str(tmp_path))
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"plan_version": 1, "recipes": [recipe]}))
    report = bl.build_library(str(plan))
    assert report == {recipe["entry_id"]: "no winner"}
    assert not (tmp_path / "library" / "index.json").exists()
    assert json.load(open(tmp_path / "library" / "build_report.json")) == report


def test_build_rejects_hash_mismatch(tmp_path, monkeypatch, recipe):
    _fake(monkeypatch, 3, sha="expected", generated_sha="other")
    entry, why = bl.build_entry(recipe["entry_id"], recipe["recipe"], str(tmp_path))
    assert entry is None and "hash differs" in why
    assert os.listdir(tmp_path) == []


def test_rerun_skips_indexed(tmp_path, monkeypatch, recipe):
    _fake(monkeypatch, 5)
    monkeypatch.setenv("TAI_OUTPUT_DIR", str(tmp_path))
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"plan_version": 1, "recipes": [recipe]}))
    bl.build_library(str(plan))
    _fake(monkeypatch, None)  # a second run must not even search
    assert bl.build_library(str(plan)) == {}
    assert len(json.load(open(tmp_path / "library" / "index.json"))["entries"]) == 1


def test_rename_retries_then_succeeds(tmp_path, monkeypatch, recipe):
    _fake(monkeypatch, 0)
    sleeps, real, calls = [], os.rename, []
    monkeypatch.setattr(bl.time, "sleep", sleeps.append)

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) < 3:
            raise PermissionError("busy")
        real(src, dst)

    monkeypatch.setattr(bl.os, "rename", flaky)
    entry, why = bl.build_entry(recipe["entry_id"], recipe["recipe"], str(tmp_path))
    assert why is None and len(calls) == 3 and sleeps == [1, 1] and os.listdir(tmp_path) == [recipe["entry_id"]]


def test_rename_gives_up_and_keeps_the_built_folder(tmp_path, monkeypatch, recipe):
    _fake(monkeypatch, 0)
    real, calls = os.rename, []
    monkeypatch.setattr(bl.time, "sleep", lambda s: None)

    def flaky(src, dst):
        if os.path.basename(dst) == recipe["entry_id"]:
            calls.append(dst)
            raise PermissionError("busy")
        real(src, dst)

    monkeypatch.setattr(bl.os, "rename", flaky)
    entry, why = bl.build_entry(recipe["entry_id"], recipe["recipe"], str(tmp_path))
    kept = tmp_path / ("_failed-" + recipe["entry_id"])
    assert entry is None and len(calls) == 5 and str(kept) in why
    assert os.listdir(tmp_path) == [kept.name] and (kept / "recipe_situation_0" / "recipe.json").exists()


def test_stray_tmp_folders_are_cleaned_at_start(tmp_path, monkeypatch, recipe):
    _fake(monkeypatch, None)
    monkeypatch.setenv("TAI_OUTPUT_DIR", str(tmp_path))
    (tmp_path / "library" / "tmpdead").mkdir(parents=True)
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"plan_version": 1, "recipes": [recipe]}))
    bl.build_library(str(plan))
    assert not (tmp_path / "library" / "tmpdead").exists()


def test_index_lock_times_out_and_is_released(tmp_path, monkeypatch):
    lib = str(tmp_path)
    open(os.path.join(lib, "index.lock"), "w").close()
    t = [0.0]
    monkeypatch.setattr(bl.time, "monotonic", lambda: t.__setitem__(0, t[0] + 4) or t[0])
    monkeypatch.setattr(bl.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="index.lock"):
        bl.update_index(lib, lambda i: None)
    os.remove(os.path.join(lib, "index.lock"))
    monkeypatch.undo()
    bl.update_index(lib, lambda i: i["entries"].append({"entry_id": "a"}))
    assert sorted(os.listdir(lib)) == ["index.json"]  # lock removed even after use, unique temp replaced


def test_index_lock_released_when_fn_raises(tmp_path):
    with pytest.raises(ValueError):
        bl.update_index(str(tmp_path), lambda i: (_ for _ in ()).throw(ValueError("x")))
    assert not os.path.exists(tmp_path / "index.lock")


def test_duration_from_video_meta(tmp_path, monkeypatch, recipe):
    _fake(monkeypatch, 0)
    real = bl.generate_from_recipe

    def with_video(r, seed, out_root, render):
        out = real(r, seed, out_root, render)[0]
        meta = json.load(open(os.path.join(out, "meta.json")))
        json.dump({**meta, "video": {"frames": 329, "fps": 10}}, open(os.path.join(out, "meta.json"), "w"))
        return (out,)

    monkeypatch.setattr(bl, "generate_from_recipe", with_video)
    entry, _ = bl.build_entry(recipe["entry_id"], recipe["recipe"], str(tmp_path))
    assert entry["duration_s"] == 32.9


def test_code_version_env_then_git(monkeypatch):
    monkeypatch.setenv("TAI_CODE_VERSION", "abc123")
    assert bl._git_head() == "abc123"
    monkeypatch.delenv("TAI_CODE_VERSION")
    monkeypatch.setattr(bl.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert bl._git_head() is None


def test_refresh_library_updates_stats_and_skips_foreign_folders(tmp_path, monkeypatch):
    monkeypatch.setenv("TAI_OUTPUT_DIR", str(tmp_path))
    lib = bl.library_dir()
    for d in ("e1", "_failed-e1", "tmp123", "stray"):
        os.makedirs(os.path.join(lib, d))
    with open(os.path.join(lib, "e1", "tracking.jsonl"), "w") as f:
        f.write(json.dumps({"t_s": 1.0}) + "\n" + json.dumps({"t_s": 4.5}) + "\n")
    with open(os.path.join(lib, "e1", "meta.json"), "w") as f:
        json.dump({}, f)
    bl.update_index(lib, lambda i: i["entries"].append(
        {"entry_id": "e1", "title": "keep", "ball_owner": "home", "goals": 0, "shots": 9, "attacker_xg": None, "duration_s": 0}))
    calls = []

    def fake_infer(d):
        calls.append("events")
        with open(os.path.join(d, "events.jsonl"), "w") as f:
            f.write(json.dumps({"type": "goal", "team": "home"}) + "\n" + json.dumps({"type": "shot", "team": "home"}) + "\n")

    def fake_analyze(d, xg, xpass, vaep=None):
        calls.append("analyze")
        os.makedirs(os.path.join(d, "interpret"), exist_ok=True)
        with open(os.path.join(d, "interpret", "events_enriched.jsonl"), "w") as f:
            f.write(json.dumps({"type": "shot", "team": "home", "xg": 0.25}) + "\n")

    monkeypatch.setattr(bl, "infer_events", fake_infer)
    monkeypatch.setattr(bl, "analyze", fake_analyze)
    monkeypatch.setattr(bl, "load_xg", lambda p: None)
    assert bl.refresh_library(log=lambda m: None) == (1, 0, 1)
    assert calls == ["events", "analyze"]
    e = bl.read_index(lib)["entries"][0]
    assert (e["title"], e["goals"], e["shots"], e["attacker_xg"], e["duration_s"]) == ("keep", 1, 1, 0.25, 3.5)
