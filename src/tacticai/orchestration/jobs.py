"""Job state under TAI_OUTPUT_DIR: create, read, write status.json, active job and the stuck-job rule."""
import json
import os
import re
import secrets
import tempfile
import time
from datetime import datetime, timedelta, timezone

JOB_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
TERMINAL = ("done", "no_winner", "failed")
STUCK_AFTER = timedelta(minutes=20)
_last = {}
STUCK_MESSAGE = "no news from the job for 20 minutes; check the container logs"


def data_dir():
    return os.environ.get("TAI_OUTPUT_DIR") or os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")


def job_dir(job_id):
    return os.path.join(data_dir(), "jobs", job_id)


def match_dir(job_id):
    return os.path.join(data_dir(), "matches", job_id)


def new_job_id():
    return f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def is_terminal(status):
    return status["state"] in TERMINAL


def read(job_id):
    """The job's status dict, or None if the job does not exist. A missing file in an existing folder is retried ~0.5 s
    (bind mounts/SMB can hide status.json for an instant after os.replace)."""
    for attempt in range(6):
        try:
            with open(os.path.join(job_dir(job_id), "status.json"), encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            if not os.path.isdir(job_dir(job_id)) or attempt == 5:
                return None
            time.sleep(0.1)


def write(job_id, **fields):
    """Merge fields into status.json atomically; rev += 1 and updated_at is refreshed."""
    # ponytail: bind mounts/SMB can hide status.json for an instant after os.replace; the running pipeline is the only writer, so its own last status is authoritative
    status = read(job_id) or _last.get(job_id)
    if status is None:
        raise FileNotFoundError(f"status.json not found for job {job_id}")
    status.update(fields)
    status["rev"] += 1
    status["updated_at"] = _now()
    path = os.path.join(job_dir(job_id), "status.json")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=job_dir(job_id), suffix=".tmp", delete=False) as f:
        json.dump(status, f)
    os.replace(f.name, path)  # unique temp per write: concurrent writers never share a file
    _last[job_id] = status
    return status


def create(request):
    """New job folder with request.json and status queued. request: {"recipe": ...} or {"library_id": ...}."""
    job_id = new_job_id()
    os.makedirs(job_dir(job_id))
    with open(os.path.join(job_dir(job_id), "request.json"), "w", encoding="utf-8") as f:
        json.dump(request, f)
    status = {"job_id": job_id, "kind": "recipe" if "recipe" in request else "library", "state": "queued",
              "progress": {"done": 0, "total": 0}, "match_id": None, "message": None, "failed_seeds": 0, "rev": 0}
    with open(os.path.join(job_dir(job_id), "status.json"), "w", encoding="utf-8") as f:
        json.dump({**status, "updated_at": _now()}, f)
    _last[job_id] = {**status, "updated_at": _now()}
    return job_id


def resolve_stuck(job_id):
    """The one stuck-job rule: published match -> done; else no update for 20 minutes -> failed."""
    status = read(job_id)
    if status is None or is_terminal(status):
        return status
    if os.path.isdir(match_dir(job_id)):
        return write(job_id, state="done", match_id=job_id)
    if datetime.now(timezone.utc) - _parse(status["updated_at"]) > STUCK_AFTER:
        return write(job_id, state="failed", message=STUCK_MESSAGE)
    return status


def active():
    """Status of the non-terminal job (after the stuck rule), or None."""
    root = os.path.join(data_dir(), "jobs")
    for job_id in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if JOB_ID_RE.match(job_id):
            status = resolve_stuck(job_id)
            if status is None and os.path.isdir(job_dir(job_id)):
                status = _last.get(job_id)  # status.json unreadable right now: do not drop a job this process knows
            if status and not is_terminal(status):
                return status
    return None
