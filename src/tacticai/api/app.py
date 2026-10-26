"""HTTP API: recipe tools, jobs with a progress WebSocket, matches and library files."""
import asyncio
import hmac
import json
import os
import math
import threading
import time
from collections import deque

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..agents import foundry
from ..orchestration import jobs
from ..explain.application import qa_agent, qa_tools
from ..ingest.application import scenario_agent
from ..ingest.application.catalog import RecipeShape, _issue, catalog, check_recipe
from ..orchestration.library import library_dir, read_index
from ..personalize.domain.lenses import CLUBS, LANGS, LENSES
from ..render.domain import director
from . import files
from ..orchestration import launcher

if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):  # lazy: without the var the package is not imported
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor()

app = FastAPI(title="tacticAI")
LOCK = threading.Lock()  # one worker, one replica: this is the whole job exclusion
SCENARIO_TIMEOUT_S = 20


def fail(status, error, detail=None, **extra):
    return JSONResponse({"error": error, "detail": detail, **extra}, status_code=status)


@app.exception_handler(StarletteHTTPException)
async def _http_error(request, exc):
    return fail(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def _bad_request(request, exc):
    return fail(422, "invalid request", [{"path": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()])


def require_key(x_access_key: str | None = Header(None)):
    """Shared key for the actions that spend money; no TAI_ACCESS_KEY = open."""
    key = os.environ.get("TAI_ACCESS_KEY")
    if key and not (x_access_key and hmac.compare_digest(x_access_key.encode(), key.encode())):
        raise HTTPException(401, "this action needs the access key")


async def body_of(request):
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise HTTPException(422, "body must be a JSON object")
    return body


@app.get("/catalog")
def get_catalog():
    return catalog()


@app.post("/recipes/validate")
async def validate_recipe(request: Request):
    body = await body_of(request)
    errors = check_recipe(body.get("recipe"))
    return {"ok": not errors, "errors": errors}


@app.post("/scenario", dependencies=[Depends(require_key)])
async def scenario(request: Request):
    body = await body_of(request)
    text, current = body.get("text"), body.get("recipe")
    if not isinstance(text, str) or not text.strip():
        return fail(422, "text is required", [_issue("text", "must be a non-empty string")])
    if len(text) > 500:
        return fail(422, "text is too long", [_issue("text", "must be at most 500 characters")])
    if current is not None:
        shape = check_recipe(current)
        if shape:
            return fail(422, "invalid current recipe", shape)
    try:
        out = await asyncio.wait_for(asyncio.to_thread(scenario_agent.draft_recipe, text, current), SCENARIO_TIMEOUT_S)
    except NotImplementedError:
        return fail(501, "the scenario agent is not implemented")
    except asyncio.TimeoutError:
        return fail(503, f"the model did not answer in {SCENARIO_TIMEOUT_S} s")
    except Exception as err:
        return fail(503, str(err))
    if not (isinstance(out, dict) and isinstance(out.get("recipe"), dict) and isinstance(out.get("summary"), str)):
        return fail(502, "the agent returned something that is not a recipe")
    try:
        RecipeShape.model_validate(out["recipe"])
    except ValidationError as err:
        return fail(502, "the agent returned a recipe with the wrong shape", str(err))
    return {"recipe": out["recipe"], "summary": out["summary"], "errors": check_recipe(out["recipe"])}


# ---- jobs ----
@app.post("/jobs", dependencies=[Depends(require_key)])
async def create_job(request: Request):
    body = await body_of(request)
    if ("recipe" in body) == ("library_id" in body):
        return fail(422, "send exactly one of recipe or library_id")
    if "recipe" in body:
        errors = check_recipe(body["recipe"])
        if errors:
            return fail(422, "invalid recipe", errors)
        req = {"recipe": body["recipe"]}
    else:
        wanted = body["library_id"]
        entry = next((e for e in read_index(library_dir())["entries"] if e["entry_id"] == wanted), None)
        if entry is None:
            return fail(422, "unknown library_id", [_issue("library_id", "not in the library")])
        if entry.get("match_id"):
            return JSONResponse({"match_id": entry["match_id"]}, status_code=200)
        req = {"library_id": entry["entry_id"]}
    return await asyncio.to_thread(_start_job, req)


def _start_job(req):
    """Blocking critical section (disk + launcher): runs in a worker thread, never on the event loop."""
    with LOCK:
        active = jobs.active()
        if active:
            return fail(409, "a job is already running", active_job_id=active["job_id"])
        job_id = jobs.create(req)
        try:
            launcher.launch(job_id)
        except Exception as err:
            jobs.write(job_id, state="failed", message=f"could not start the job: {err}")
    return JSONResponse({"job_id": job_id}, status_code=202)


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    status = jobs.JOB_ID_RE.match(job_id) and jobs.resolve_stuck(job_id)
    if not status:
        raise HTTPException(404, "job not found")
    return status


@app.websocket("/ws/jobs/{job_id}")
async def job_socket(ws: WebSocket, job_id: str):
    await ws.accept()
    status = jobs.JOB_ID_RE.match(job_id) and jobs.resolve_stuck(job_id)
    if not status:
        await ws.close(code=1008)
        return
    async def poll(status):
        await ws.send_json(status)
        while not jobs.is_terminal(status):
            await asyncio.sleep(0.5)
            latest = jobs.resolve_stuck(job_id)
            if latest and latest["rev"] != status["rev"]:  # None: status.json unreadable this tick, skip it
                status = latest
                await ws.send_json(status)

    async def until_disconnect():
        while (await ws.receive())["type"] != "websocket.disconnect":
            pass

    poller, gone = asyncio.create_task(poll(status)), asyncio.create_task(until_disconnect())
    try:
        await asyncio.wait({poller, gone}, return_when=asyncio.FIRST_COMPLETED)
        if poller.done() and not poller.cancelled():
            poller.result()
            await ws.close()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        for t in (poller, gone):
            t.cancel()


# ---- files ----
def _send(kind, ident, name):
    path = files.resolve(kind, ident, name)
    if path is None:
        raise HTTPException(404, "file not found")
    return FileResponse(path, media_type=files.MEDIA.get(os.path.splitext(path)[1]), headers={"Cache-Control": "no-cache"})  # FileResponse handles Range


def _duration(meta):
    video = meta.get("video") or {}
    return round(video.get("frames", 0) / video["fps"], 1) if video.get("fps") else 0.0


@app.get("/matches")
def list_matches():
    root, out = files.roots()["matches"], []
    for d in sorted(os.listdir(root), reverse=True) if os.path.isdir(root) else []:
        path = files.resolve("matches", d, "meta.json")
        if path:
            with open(path, encoding="utf-8") as f:
                meta = json.load(f)
            out.append({"match_id": d, "teams": meta["teams"], "formations": meta["formations"],
                        "duration_s": _duration(meta), "library_id": meta.get("library_id"), "featured": False})
    named = os.environ.get("TAI_FEATURED_MATCH")
    pick = next((m for m in out if m["match_id"] == named), None) if named else next((m for m in out if m["library_id"]), None)
    if pick:
        pick["featured"] = True
    return out


def _read(match_id, name):
    """Parsed file of a match (.json or .jsonl) through the common resolver, else None."""
    path = files.resolve("matches", match_id, name)
    if path is None:
        return None
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()] if name.endswith(".jsonl") else json.load(f)


@app.get("/matches/{match_id}/overlays")
def overlays(match_id: str, lens: str = "fan", lang: str = "en", club: str = "neutral", player: str | None = None,
             metric: str | None = None, brand: str = "tacticai"):
    if files.resolve("matches", match_id, "meta.json") is None:
        raise HTTPException(404, "match not found")
    for name, value, valid in (("lens", lens, list(LENSES)), ("lang", lang, list(LANGS)), ("club", club, list(CLUBS)), ("brand", brand, list(director.BRANDS))):
        if value not in valid:
            return fail(422, f"invalid {name}", [_issue(name, f"must be one of {valid}")])
    roster = {p["player_id"]: p for p in (_read(match_id, "roster.json") or {"players": []})["players"]}
    if player is not None and player not in roster:
        return fail(422, "invalid player", [_issue("player", "not in the roster of the match")])
    if metric is not None and (lens != "one_metric" or metric not in director.METRIC_KINDS):
        return fail(422, "invalid metric", [_issue("metric", f"only with lens=one_metric, one of {list(director.METRIC_KINDS)}")])
    text_lens = LENSES[lens]["text"]
    models = (_read(match_id, "interpret/meta.json") or {}).get("models", {})
    try:
        out = director.assemble_overlays(
            _read(match_id, "explain/insights.jsonl"), {f"{lens}_{club}": _read(match_id, f"render/plans/{lens}_{club}.json")} if lens != "one_metric" else {},
            {f"{text_lens}_{lang}_{club}": _read(match_id, f"personalize/variants/{text_lens}_{lang}_{club}.json")}, lens, lang, club, player, metric, brand,
            roster, _read(match_id, "interpret/players.json"), _read(match_id, "interpret/timeline.jsonl"), _read(match_id, "interpret/events_enriched.jsonl"),
            models.get("vaep") is not None)
    except ValueError as err:
        return fail(422, str(err))
    return JSONResponse(out, headers={"Cache-Control": "no-cache"})


# ---- Match Q&A: limits per spec (one query at a time, 30 per hour, 20 s deadline) ----
ASK_DEADLINE_S, ASK_GUARD_S, ASK_PER_HOUR = 20, 25, 30
_ask = {"busy_since": None, "token": None, "times": deque()}  # ponytail: per process, one replica; shared store if it scales


def _ask_worker(token, match_id, question, lang):
    try:
        session = qa_tools.QASession(_read(match_id, "explain/insights.jsonl") or [], _read(match_id, "interpret/events_enriched.jsonl") or [])
        meta = _read(match_id, "meta.json") or {}
        context = {"teams": meta.get("teams"), "players": (_read(match_id, "roster.json") or {}).get("players", []), "max_tool_calls": session.max_tool_calls,
                   "max_output_tokens": session.max_output_tokens, "deadline_s": ASK_DEADLINE_S}
        out = qa_agent.answer_question(question, lang, session, context)
        return qa_tools.validate_answer(out, session, lang)
    finally:
        if _ask["token"] == token:
            _ask["busy_since"] = _ask["token"] = None


@app.post("/matches/{match_id}/ask", dependencies=[Depends(require_key)])
async def ask(match_id: str, request: Request):
    if files.resolve("matches", match_id, "meta.json") is None:
        raise HTTPException(404, "match not found")
    body = await body_of(request)
    question, lang = body.get("question"), body.get("lang")
    if not isinstance(question, str) or not 1 <= len(question.strip()) or len(question) > 500:
        return fail(422, "invalid question", [_issue("question", "must be 1 to 500 characters")])
    if lang not in LANGS:
        return fail(422, "invalid lang", [_issue("lang", f"must be one of {list(LANGS)}")])
    if getattr(qa_agent.answer_question, "needs_foundry", False) and not foundry.configured():
        return fail(501, "the Q&A agent is not implemented")
    now = time.monotonic()
    if _ask["busy_since"] is not None and now - _ask["busy_since"] < ASK_GUARD_S:
        return fail(429, "a question is already being answered", retry_after_s=1)
    times = _ask["times"]
    while times and now - times[0] >= 3600:
        times.popleft()
    if len(times) >= ASK_PER_HOUR:
        return fail(429, "too many questions this hour", retry_after_s=math.ceil(3600 - (now - times[0])))
    times.append(now)
    token = _ask["token"] = object()
    _ask["busy_since"] = now
    try:
        result, errors = await asyncio.wait_for(asyncio.to_thread(_ask_worker, token, match_id, question, lang), ASK_DEADLINE_S)
    except NotImplementedError:
        return fail(501, "the Q&A agent is not implemented")
    except asyncio.TimeoutError:
        return fail(503, f"the model did not answer in {ASK_DEADLINE_S} s")
    except Exception as err:
        return fail(503, str(err))
    if errors:
        return fail(502, "the agent returned an answer that does not validate", errors)
    return result


@app.get("/matches/{match_id}/files/{name:path}")
def match_file(match_id: str, name: str):
    return _send("matches", match_id, name)


@app.get("/library")
def library():
    return read_index(library_dir())


@app.get("/library/{entry_id}/files/{name:path}")
def library_file(entry_id: str, name: str):
    return _send("library", entry_id, name)


UI_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ui", "dist"))
if os.path.isdir(UI_DIST):
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
