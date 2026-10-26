import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from tacticai.orchestration import jobs


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("TAI_OUTPUT_DIR", str(tmp_path))


def age(job_id, minutes):
    old = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="milliseconds")
    path = os.path.join(jobs.job_dir(job_id), "status.json")
    s = json.load(open(path))
    s["updated_at"] = old.replace("+00:00", "Z")
    json.dump(s, open(path, "w"))


def test_create_and_write():
    job_id = jobs.create({"recipe": {}})
    assert jobs.JOB_ID_RE.match(job_id)
    s = jobs.read(job_id)
    assert (s["kind"], s["state"], s["rev"]) == ("recipe", "queued", 0)
    s = jobs.write(job_id, state="searching", progress={"done": 1, "total": 5})
    assert (s["rev"], jobs.read(job_id)["progress"]["done"]) == (1, 1)
    assert s["updated_at"].endswith("Z") and len(s["updated_at"]) == 24
    assert not os.path.exists(os.path.join(jobs.job_dir(job_id), "status.json.tmp"))
    assert jobs.read(jobs.create({"library_id": "x"}))["kind"] == "library"


def test_active_job():
    assert jobs.active() is None
    job_id = jobs.create({"recipe": {}})
    assert jobs.active()["job_id"] == job_id
    jobs.write(job_id, state="done")
    assert jobs.active() is None


def test_stuck_published_match_is_done():
    job_id = jobs.create({"recipe": {}})
    jobs.write(job_id, state="analyzing")
    os.makedirs(jobs.match_dir(job_id))
    s = jobs.resolve_stuck(job_id)
    assert (s["state"], s["match_id"]) == ("done", job_id)


def test_stuck_after_20_minutes_is_failed():
    job_id = jobs.create({"recipe": {}})
    age(job_id, 19)
    assert jobs.resolve_stuck(job_id)["state"] == "queued"
    age(job_id, 21)
    s = jobs.resolve_stuck(job_id)
    assert (s["state"], s["message"]) == ("failed", jobs.STUCK_MESSAGE)
    assert jobs.active() is None


def test_write_survives_transient_missing_status(monkeypatch):
    job_id = jobs.create({"recipe": {}})
    jobs.write(job_id, state="searching")
    real = jobs.read
    calls = []
    monkeypatch.setattr(jobs, "read", lambda j: None if not calls and not calls.append(1) else real(j))
    assert jobs.write(job_id, state="analyzing")["rev"] == 2
    assert real(job_id)["rev"] == 2


def test_write_unknown_job_raises():
    with pytest.raises(FileNotFoundError, match="status.json not found"):
        jobs.write("20000101-000000-abcd", state="x")


def test_read_retries_when_status_is_transiently_missing(monkeypatch):
    job_id = jobs.create({"recipe": {}})
    real, calls = open, []

    def flaky(path, *a, **k):
        if str(path).endswith("status.json") and len(calls) < 2:
            calls.append(1)
            raise FileNotFoundError(path)
        return real(path, *a, **k)
    monkeypatch.setattr("builtins.open", flaky)
    monkeypatch.setattr(jobs.time, "sleep", lambda s: None)
    assert jobs.read(job_id)["job_id"] == job_id and len(calls) == 2
    assert jobs.read("20000101-000000-abcd") is None  # no folder: no retry


def test_active_keeps_a_job_whose_status_is_unreadable(monkeypatch):
    job_id = jobs.create({"recipe": {}})
    monkeypatch.setattr(jobs, "read", lambda j: None)
    assert jobs.active()["job_id"] == job_id


def test_write_uses_a_unique_temp_file(monkeypatch):
    job_id = jobs.create({"recipe": {}})
    seen = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (seen.append(a), real(a, b)))
    jobs.write(job_id, state="searching")
    jobs.write(job_id, state="analyzing")
    assert len(set(seen)) == 2 and all(s.endswith(".tmp") and not s.endswith("status.json.tmp") for s in seen)
    assert os.listdir(jobs.job_dir(job_id)).count("status.json") == 1 and not [f for f in os.listdir(jobs.job_dir(job_id)) if f.endswith(".tmp")]


def test_stages_record_first_time_of_each_state():
    job_id = jobs.create({"recipe": {}})
    assert list(jobs.read(job_id)["stages"]) == ["queued"]
    first = jobs.write(job_id, state="searching", progress={"done": 0, "total": 3})["stages"]["searching"]
    jobs.write(job_id, state="searching", progress={"done": 2, "total": 3})
    jobs.write(job_id, progress={"done": 3, "total": 3})
    s = jobs.write(job_id, state="rendering")
    assert s["stages"]["searching"] == first and list(s["stages"]) == ["queued", "searching", "rendering"]
