import json
import os

import pytest
from fastapi.testclient import TestClient

from tacticai.orchestration import jobs
from tacticai.api import app as api
from tacticai.api import files
from tacticai.orchestration import launcher
from tacticai.orchestration import library as bl
from tacticai.ingest.domain.pitch import ENG_X

RECIPE = {"mode": "situation", "home": {}, "away": {},
          "situation": {"template": "counter", "ball_owner": "home", "wanted": ["goal_by_team:home"]}, "seeds": 2}


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("TAI_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "launch", lambda job_id: None)


@pytest.fixture
def client():
    return TestClient(api.app)


def publish_match(job_id, **meta):
    d = jobs.match_dir(job_id)
    os.makedirs(os.path.join(d, "interpret"))
    json.dump({"teams": {"home": {"name": "A", "short": "A"}, "away": {"name": "B", "short": "B"}},
               "formations": {"home": "4-4-2", "away": "4-3-3"}, "video": {"fps": 10, "frames": 100}, **meta},
              open(os.path.join(d, "meta.json"), "w"))
    open(os.path.join(d, "interpret", "timeline.jsonl"), "w").write('{"t": 0}\n')
    open(os.path.join(d, "video.mp4"), "wb").write(bytes(range(256)) * 2)
    return d


def test_home_list_is_422_with_path(client):
    r = client.post("/recipes/validate", json={"recipe": {**RECIPE, "home": []}})
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["errors"][0]["path"] == "home"
    r = client.post("/jobs", json={"recipe": {**RECIPE, "home": []}})
    assert r.status_code == 422 and r.json()["detail"][0]["path"] == "home" and r.json()["error"]


def test_domain_error_has_path(client):
    bad = {**RECIPE, "home": {"formation": "9-9-9"}}
    r = client.post("/recipes/validate", json={"recipe": bad})
    assert r.json()["errors"] == [{"path": "home.formation", "message": "unknown formation '9-9-9'"}]
    assert client.post("/recipes/validate", json={"recipe": RECIPE}).json() == {"ok": True, "errors": []}


def test_path_traversal_is_404(client):
    jid = "20261023-181502-a3f1"
    publish_match(jid)
    for bad in ("..%2F..", "%2e%2e", "..", "a%2F..%2Fb"):
        assert client.get(f"/matches/{bad}/files/meta.json").status_code == 404
    assert client.get(f"/matches/{jid}/files/..%2Fmeta.json").status_code == 404
    assert client.get(f"/matches/{jid}/files/interpret/../meta.json").status_code in (200, 404)
    assert client.get(f"/matches/{jid}/files/status.json").status_code == 404
    assert files.resolve("matches", "../x", "meta.json") is None
    assert files.resolve("matches", jid, "../../x") is None
    assert files.resolve("library", "nope", "meta.json") is None


def test_timeline_is_served(client):
    jid = "20261023-181502-a3f1"
    publish_match(jid)
    r = client.get(f"/matches/{jid}/files/interpret/timeline.jsonl")
    assert r.status_code == 200 and r.text.strip() == '{"t": 0}'
    assert client.get(f"/matches/{jid}/files/interpret/phases.jsonl").status_code == 404  # allowed name, file absent


def test_range_gives_206(client):
    jid = "20261023-181502-a3f1"
    publish_match(jid)
    r = client.get(f"/matches/{jid}/files/video.mp4", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100 and r.headers["content-range"] == "bytes 0-99/512"
    assert r.headers["cache-control"] == "no-cache"


def test_matches_list(client):
    jid = "20261023-181502-a3f1"
    publish_match(jid, library_id="counter-home-goal-01")
    (m,) = client.get("/matches").json()
    assert (m["match_id"], m["duration_s"], m["library_id"]) == (jid, 10.0, "counter-home-goal-01")


def test_featured_flag(client, monkeypatch):
    publish_match("20261023-181502-a3f1", library_id="counter-home-goal-01")
    publish_match("20261024-181502-a3f2")
    publish_match("20261022-181502-a3f3", library_id="counter-home-goal-02")
    flags = {m["match_id"]: m["featured"] for m in client.get("/matches").json()}
    assert flags == {"20261024-181502-a3f2": False, "20261023-181502-a3f1": True, "20261022-181502-a3f3": False}
    monkeypatch.setenv("TAI_FEATURED_MATCH", "20261022-181502-a3f3")
    assert [m["match_id"] for m in client.get("/matches").json() if m["featured"]] == ["20261022-181502-a3f3"]


def test_featured_none_without_library_match(client):
    publish_match("20261024-181502-a3f2")
    assert [m["featured"] for m in client.get("/matches").json()] == [False]


def enriched_match(job_id="20261024-000000-aaaa"):
    from pathlib import Path
    import shutil
    from tacticai.explain.application import build_insights as B
    from tacticai.personalize.application import build_personalize
    from tacticai.render.application import plans
    d = jobs.match_dir(job_id)
    shutil.copytree(Path(__file__).parents[1] / "explain" / "fixtures" / "match", d)
    B.run(d, context={})
    build_personalize.run(d, context={})
    plans.run(d, context={})
    return d


def test_overlays_defaults(client):
    enriched_match()
    r = client.get("/matches/20261024-000000-aaaa/overlays")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    body = r.json()
    assert (body["available"], body["lens"], body["lang"], body["club"], body["brand"], body["metric"], body["player"]) == (True, "fan", "en", "neutral", "tacticai", None, None)
    assert body["metric_series"] is None and body["brand_tokens"] is None
    assert client.get("/matches/20261024-000000-aaaa/overlays?lens=broadcast&brand=bka-tv").json()["brand_tokens"]["name"]
    assert client.get("/matches/20261024-000000-aaaa/overlays?lens=one_metric").json()["metric"] == "pressure"


def test_overlays_es_uses_decimal_comma(client):
    enriched_match()
    es = client.get("/matches/20261024-000000-aaaa/overlays?lens=analyst&lang=es").json()
    en = client.get("/matches/20261024-000000-aaaa/overlays?lens=analyst&lang=en").json()
    es_text, en_text = " ".join(o["title"] + " " + o["text"] for o in es["overlays"]), " ".join(o["title"] + " " + o["text"] for o in en["overlays"])
    assert "0,34" in es_text and "0.34" not in es_text and "0.34" in en_text


def test_render_assets_are_served_with_range(client):
    d = enriched_match()
    os.makedirs(os.path.join(d, "render", "clips"))
    for n, body in (("heatmaps.json", b"{}"), ("clips/manifest.json", b"{}"), ("clips/i002.mp4", b"0123456789")):
        open(os.path.join(d, "render", n), "wb").write(body)
    base = "/matches/20261024-000000-aaaa/files/render/"
    assert client.get(base + "heatmaps.json").status_code == 200 and client.get(base + "clips/manifest.json").status_code == 200
    r = client.get(base + "clips/i002.mp4", headers={"Range": "bytes=2-4"})
    assert (r.status_code, r.content, r.headers["content-type"]) == (206, b"234", "video/mp4")
    assert client.get(base + "clips/i2.mp4").status_code == 404


def test_overlays_errors(client):
    enriched_match()
    base = "/matches/20261024-000000-aaaa/overlays"
    assert client.get("/matches/20261024-000000-bbbb/overlays").status_code == 404
    assert client.get("/matches/20261024-000000-bbbb/overlays?lens=nope").status_code == 404
    assert client.get(base + "?lens=nope").status_code == 422
    assert client.get(base + "?lang=fr").status_code == 422
    assert client.get(base + "?player=../../etc").status_code == 422
    assert client.get(base + "?player=nobody").status_code == 422
    assert client.get(base + "?metric=xg").status_code == 422
    assert client.get(base + "?lens=one_metric&metric=bad").status_code == 422
    assert client.get(base + "?lens=one_metric&metric=xg").status_code == 200


def test_overlays_not_enriched(client):
    publish_match("20261024-000000-cccc")
    r = client.get("/matches/20261024-000000-cccc/overlays")
    assert r.status_code == 200 and r.json() == {"available": False, "reason": "not_enriched"}


def test_new_files_are_served_only_by_pattern(client):
    enriched_match()
    base = "/matches/20261024-000000-aaaa/files/"
    assert client.get(base + "explain/insights.jsonl").status_code == 200
    assert client.get(base + "personalize/variants/fan_es_home.json").status_code == 200
    assert client.get(base + "render/plans/broadcast_neutral.json").status_code == 200
    assert client.get(base + "render/plans/one_metric_neutral.json").status_code == 404
    assert client.get(base + "explain/../../../../etc/passwd").status_code == 404
    assert client.get("/library/counter-home-goal-01/files/explain/insights.jsonl").status_code == 404


def test_away_template_preview_on_the_correct_side(client):
    prev = client.get("/catalog").json()["template_previews"]["counter"]
    assert set(prev) == {"home", "away"}
    # counter, ball_owner home: the home GK sits at x=-1.0 (own goal on the left), the away GK on the right
    assert [p["x"] for p in prev["home"]["home"] if p["role"] == "GK"] == [-ENG_X]
    assert [p["x"] for p in prev["home"]["away"] if p["role"] == "GK"] == [ENG_X]
    # ball_owner away: the away team attacks towards -x, the ball is mirrored (x was -0.13 for the home owner)
    assert prev["away"]["ball"]["x"] == pytest.approx(0.13 * ENG_X, abs=0.01) and prev["home"]["ball"]["x"] < 0
    away_cf = [p for p in prev["away"]["away"] if p["role"] == "CF"][0]
    assert away_cf["x"] == pytest.approx(-0.12 * ENG_X, abs=0.01)
    assert all(len(prev[o][t]) == 11 for o in prev for t in ("home", "away"))
    cat = client.get("/catalog").json()
    assert len(cat["examples"]) == 3 and "4-4-2" in cat["formations"] and cat["players"] == []


def test_scenario_stub_is_501_and_errors(client, monkeypatch):
    assert client.post("/scenario", json={"text": "counter", "recipe": None}).status_code == 501
    assert client.post("/scenario", json={"text": "  "}).status_code == 422
    assert client.post("/scenario", json={"text": "x" * 501}).status_code == 422
    assert client.post("/scenario", json={"text": "x", "recipe": {**RECIPE, "away": []}}).status_code == 422
    monkeypatch.setattr(api.scenario_agent, "draft_recipe", lambda text, recipe=None: {"nope": 1})
    assert client.post("/scenario", json={"text": "x"}).status_code == 502
    monkeypatch.setattr(api.scenario_agent, "draft_recipe", lambda text, recipe=None: 1 / 0)
    assert client.post("/scenario", json={"text": "x"}).status_code == 503
    bad = {**RECIPE, "home": {"formation": "9-9-9"}}
    monkeypatch.setattr(api.scenario_agent, "draft_recipe", lambda text, recipe=None: {"recipe": bad, "summary": "s"})
    r = client.post("/scenario", json={"text": "x"})
    assert r.status_code == 200 and r.json()["errors"][0]["path"] == "home.formation"
    monkeypatch.setattr(api.scenario_agent, "draft_recipe", lambda text, recipe=None: {"recipe": RECIPE, "summary": "s"})
    assert client.post("/scenario", json={"text": "x"}).json()["errors"] == []


def test_second_post_is_409_with_active_job(client):
    first = client.post("/jobs", json={"recipe": RECIPE})
    assert first.status_code == 202
    second = client.post("/jobs", json={"recipe": RECIPE})
    assert second.status_code == 409 and second.json()["active_job_id"] == first.json()["job_id"]
    assert client.get(f"/jobs/{first.json()['job_id']}").json()["state"] == "queued"
    assert client.get("/jobs/nope").status_code == 404


def test_failing_launcher_marks_failed(client, monkeypatch):
    def boom(job_id):
        raise OSError("docker not found")
    monkeypatch.setattr(launcher, "launch", boom)
    r = client.post("/jobs", json={"recipe": RECIPE})
    assert r.status_code == 202
    s = client.get(f"/jobs/{r.json()['job_id']}").json()
    assert s["state"] == "failed" and "docker not found" in s["message"]
    assert client.post("/jobs", json={"recipe": RECIPE}).status_code == 202  # the failed job no longer blocks


def test_ws_sends_initial_and_terminal_state(client):
    job_id = jobs.create({"recipe": RECIPE})
    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        assert ws.receive_json()["state"] == "queued"
        jobs.write(job_id, state="searching", progress={"done": 1, "total": 2})
        assert ws.receive_json()["state"] == "searching"
        jobs.write(job_id, state="done", match_id=job_id)
        last = ws.receive_json()
        assert (last["state"], last["match_id"]) == ("done", job_id)
    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:  # already terminal: one message, then close
        assert ws.receive_json()["state"] == "done"


def library_entry(entry_id="counter-home-goal-01", match_id=None):
    os.makedirs(os.path.join(bl.library_dir(), entry_id))
    open(os.path.join(bl.library_dir(), entry_id, "recipe.json"), "w").write("{}")
    bl.update_index(bl.library_dir(), lambda i: i["entries"].append({"entry_id": entry_id, "match_id": match_id}))
    return entry_id


def test_library_post_twice_returns_same_match(client):
    entry_id = library_entry()
    assert client.post("/jobs", json={"library_id": "counter-home-goal-02"}).status_code == 422
    r = client.post("/jobs", json={"library_id": entry_id})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    assert jobs.read(job_id)["kind"] == "library"
    # what the pipeline does when it finishes
    jobs.write(job_id, state="done", match_id=job_id)
    bl.update_index(bl.library_dir(), lambda i: i["entries"][0].update(match_id=job_id))
    again = client.post("/jobs", json={"library_id": entry_id})
    assert again.status_code == 200 and again.json() == {"match_id": job_id}
    assert client.get("/library").json()["entries"][0]["match_id"] == job_id
    assert client.get(f"/library/{entry_id}/files/recipe.json").status_code == 200
    assert client.get(f"/library/{entry_id}/files/video.mp4").status_code == 404


def test_library_empty_and_bad_bodies(client):
    assert client.get("/library").json()["entries"] == []
    assert client.post("/jobs", json={}).status_code == 422
    assert client.post("/jobs", content=b"not json").status_code == 422
    assert client.post("/jobs", json={"library_id": 5}).status_code == 422


def test_malformed_positions_are_422_not_500(client):
    pl = [[0, 0, {}]] * 11
    bad = {**RECIPE, "situation": {**RECIPE["situation"], "positions": {"home": pl, "away": []}}}
    r = client.post("/recipes/validate", json={"recipe": bad})
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["errors"][0]["path"] == "situation.positions"
    assert client.post("/jobs", json={"recipe": bad}).status_code == 422
    assert client.post("/recipes/validate", json={"recipe": {**RECIPE, "situation": {"positions": {"home": [5], "away": []}}}}).json()["ok"] is False


def test_product_limits(client):
    def errs(recipe):
        return client.post("/recipes/validate", json={"recipe": recipe}).json()["errors"]
    assert errs({**RECIPE, "home": {"level": 0.1}}) == [{"path": "home.level", "message": "level must be in 0.7..1.0"}]
    assert errs({**RECIPE, "steps": 3000})[0]["path"] == "steps"
    assert errs({"mode": "full_match", "away": {"level": 0.5}})[0]["path"] == "away.level"
    assert errs({"mode": "full_match", "steps": 1000, "home": {"level": 0.7}}) == []
    assert client.post("/jobs", json={"recipe": {**RECIPE, "steps": 3000}}).status_code == 422


def test_aca_failure_of_the_start_poller_marks_failed(monkeypatch):
    import sys
    import types
    import threading
    job_id = jobs.create({"recipe": RECIPE})

    class Poller:
        def result(self):
            raise RuntimeError("start failed")
    client_cls = lambda cred, sub: types.SimpleNamespace(jobs=types.SimpleNamespace(begin_start=lambda rg, name: Poller()))
    monkeypatch.setitem(sys.modules, "azure.identity", types.SimpleNamespace(DefaultAzureCredential=lambda: None))
    monkeypatch.setitem(sys.modules, "azure.mgmt.appcontainers", types.SimpleNamespace(ContainerAppsAPIClient=client_cls))
    for k, v in {"TAI_RUNNER": "aca", "AZURE_SUBSCRIPTION_ID": "s", "AZURE_RESOURCE_GROUP": "g", "TAI_JOB_NAME": "j"}.items():
        monkeypatch.setenv(k, v)
    launcher._aca(job_id)  # launcher.launch is patched by the autouse fixture: call _aca directly
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon:
            t.join(2)
    s = jobs.read(job_id)
    assert s["state"] == "failed" and "start failed" in s["message"]


def test_ws_tolerates_unreadable_status_and_stops_on_disconnect(client, monkeypatch):
    job_id = jobs.create({"recipe": RECIPE})
    real, calls = jobs.resolve_stuck, []

    def flaky(j):
        calls.append(1)
        return None if len(calls) == 2 else real(j)
    monkeypatch.setattr(jobs, "resolve_stuck", flaky)
    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        assert ws.receive_json()["state"] == "queued"
        jobs.write(job_id, state="done", match_id=job_id)
        assert ws.receive_json()["state"] == "done"  # the None tick was skipped, no crash
    assert len(calls) >= 3
    polls = []
    monkeypatch.setattr(jobs, "resolve_stuck", lambda j: polls.append(1) or real(j))
    job2 = jobs.create({"recipe": RECIPE})
    with client.websocket_connect(f"/ws/jobs/{job2}") as ws:
        assert ws.receive_json()["state"] == "queued"
    import time
    time.sleep(1.2)
    n = len(polls)
    time.sleep(1.2)
    assert len(polls) == n  # the client is gone: polling stopped


# ---- Match Q&A (/ask) ----
import time  # noqa: E402

from tacticai.explain.application import qa_agent  # noqa: E402

EVENTS = [{"type": "goal", "t_s": 24.3, "clock_s": 314.0, "period": 1, "team": "home", "player_id": "home-09"},
          {"type": "pass", "t_s": 30.0, "clock_s": 320.0, "period": 1, "team": "home", "player_id": "home-01"}]


@pytest.fixture
def ask_match():
    d = publish_match("20261024-120000-aaaa")
    with open(os.path.join(d, "interpret", "events_enriched.jsonl"), "w") as f:
        f.writelines(json.dumps(e) + "\n" for e in EVENTS)
    return "20261024-120000-aaaa"


@pytest.fixture(autouse=True)
def reset_ask():
    api._ask.update(busy_since=None, token=None)
    api._ask["times"].clear()


def real_agent(monkeypatch, fn):
    monkeypatch.setattr(qa_agent, "answer_question", fn)


def ask(client, mid, q="every goal", lang="en"):
    return client.post(f"/matches/{mid}/ask", json={"question": q, "lang": lang})


def good_agent(question, lang, tools, ctx):
    n = tools.count_events(type="goal")["count"]
    items = tools.search_events(type="goal")["items"]
    return {"answer": "There was {n|goal|goals}: {n}", "values": {"n": n}, "moments": [{"kind": "event", "event_index": items[0]["event_index"]}]}


def test_ask_404_422_501(client, ask_match):
    assert ask(client, "20261024-120000-bbbb").status_code == 404
    assert ask(client, ask_match, q="").status_code == 422
    assert ask(client, ask_match, q="x" * 501).status_code == 422
    assert ask(client, ask_match, lang="fr").status_code == 422
    assert ask(client, ask_match).status_code == 501  # the stub
    assert len(api._ask["times"]) == 0


def test_ask_happy_path(client, ask_match, monkeypatch):
    real_agent(monkeypatch, good_agent)
    r = ask(client, ask_match)
    assert r.status_code == 200
    assert r.json()["values"] == {"n": 1}
    assert r.json()["moments"] == [{"kind": "event", "event_index": 0, "t_s": 24.3, "clock_s": 314.0, "period": 1}]
    assert api._ask["busy_since"] is None


def test_ask_502_on_reference_no_tool_returned(client, ask_match, monkeypatch):
    real_agent(monkeypatch, lambda q, l, t, c: (t.count_events(type="goal"), {"answer": "ok", "values": {}, "moments": [{"kind": "event", "event_index": 1}]})[1])
    assert ask(client, ask_match).status_code == 502


def test_ask_503_on_timeout_and_429_while_busy(ask_match, monkeypatch):
    with TestClient(api.app) as client:  # one event loop for both requests: a per-request loop would wait for the thread
        _timeout_then_busy(client, ask_match, monkeypatch)


def _timeout_then_busy(client, ask_match, monkeypatch):
    monkeypatch.setattr(api, "ASK_DEADLINE_S", 0.2)
    real_agent(monkeypatch, lambda q, l, t, c: time.sleep(0.6))
    assert ask(client, ask_match).status_code == 503
    r = ask(client, ask_match)  # the first thread is still running
    assert r.status_code == 429 and r.json()["retry_after_s"]
    time.sleep(0.8)
    real_agent(monkeypatch, good_agent)
    assert ask(client, ask_match).status_code == 200


def test_ask_429_hourly(client, ask_match, monkeypatch):
    real_agent(monkeypatch, good_agent)
    for _ in range(30):
        assert ask(client, ask_match).status_code == 200
    r = ask(client, ask_match)
    assert r.status_code == 429 and 0 < r.json()["retry_after_s"] <= 3600


def test_job_frame_is_the_last_complete_line(client):
    job_id = jobs.create({"recipe": RECIPE})
    assert client.get(f"/jobs/{job_id}/frame").status_code == 404
    d = os.path.join(jobs.job_dir(job_id), "staging", "recipe_situation_0")
    os.makedirs(d)
    open(os.path.join(d, "tracking.jsonl"), "w").write('{"frame_index": 1}\n{"frame_index": 2}\n{"frame_in')
    assert client.get(f"/jobs/{job_id}/frame").json() == {"frame_index": 2}
    assert client.get("/jobs/nope/frame").status_code == 404


def test_models_has_three_cards(client):
    models = client.get("/models").json()["models"]
    assert [m["id"] for m in models] == ["xg_v1", "xpass_v1", "vaep_v1"]
    assert all(m["features"] and m["test"]["auc"] > 0 for m in models)
    vaep = models[2]
    assert vaep["concedes"]["test"]["auc"] > 0 and vaep["concedes"]["baseline"]["auc"] > 0
    assert "concedes" not in models[0]


def test_preview_route(client):
    jid = jobs.create({"recipe": {}})
    path = os.path.join(jobs.job_dir(jid), "preview.jpg")
    assert client.get("/jobs/nope/preview.jpg").status_code == 404
    assert client.get("/jobs/20261024-000000-ffff/preview.jpg").status_code == 404
    assert client.get(f"/jobs/{jid}/preview.jpg").status_code == 404
    whole = b"\xff\xd8jpeg\xff\xd9"
    open(path, "wb").write(whole)
    r = client.get(f"/jobs/{jid}/preview.jpg")
    assert (r.status_code, r.headers["content-type"], r.headers["cache-control"], r.content) == (200, "image/jpeg", "no-store", whole)
    open(path, "wb").write(b"\xff\xd8half")  # ffmpeg mid-write
    assert client.get(f"/jobs/{jid}/preview.jpg").content == whole
