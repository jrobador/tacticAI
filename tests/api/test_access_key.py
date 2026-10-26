import pytest
from fastapi.testclient import TestClient

from tacticai.api import app as api
from tacticai.orchestration import launcher

GUARDED = [("/scenario", {"text": "x"}), ("/jobs", {}), ("/matches/m1/ask", {"question": "q", "lang": "en"})]


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("TAI_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "launch", lambda job_id: None)


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.mark.parametrize("path,body", GUARDED)
def test_key_required(client, monkeypatch, path, body):
    monkeypatch.setenv("TAI_ACCESS_KEY", "s3cret")
    missing = client.post(path, json=body)
    assert missing.status_code == 401 and missing.json()["error"] == "this action needs the access key"
    assert client.post(path, json=body, headers={"X-Access-Key": "nope"}).status_code == 401
    assert client.post(path, json=body, headers={"X-Access-Key": "s3cret"}).status_code != 401


@pytest.mark.parametrize("path,body", GUARDED)
def test_open_without_env(client, monkeypatch, path, body):
    monkeypatch.delenv("TAI_ACCESS_KEY", raising=False)
    assert client.post(path, json=body).status_code != 401


def test_reads_stay_open(client, monkeypatch):
    monkeypatch.setenv("TAI_ACCESS_KEY", "s3cret")
    assert client.get("/catalog").status_code == 200
    assert client.get("/matches").status_code == 200
