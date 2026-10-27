import io

import pytest
from fastapi.testclient import TestClient

from tacticai.api import app as api, speech


@pytest.fixture
def client():
    return TestClient(api.app)


def test_token(client, monkeypatch):
    monkeypatch.setenv("FOUNDRY_API_KEY", "k")
    monkeypatch.setenv("FOUNDRY_ENDPOINT", "https://myres.services.ai.azure.com/api/projects/p")
    seen = {}

    def fake(req, timeout):
        seen["url"], seen["key"] = req.full_url, req.get_header("Ocp-apim-subscription-key")
        return io.BytesIO(b"tok123")
    monkeypatch.setattr(speech.urllib.request, "urlopen", fake)
    r = client.get("/speech/token")
    assert r.json() == {"token": "tok123", "region": "brazilsouth"}
    assert seen == {"url": "https://myres.cognitiveservices.azure.com/sts/v1.0/issueToken", "key": "k"}


def test_not_configured(client, monkeypatch):
    monkeypatch.delenv("FOUNDRY_API_KEY", raising=False)
    r = client.get("/speech/token")
    assert r.status_code == 503 and r.json()["error"] == "Speech is not configured"


def test_azure_failure(client, monkeypatch):
    monkeypatch.setenv("FOUNDRY_API_KEY", "k")
    monkeypatch.setenv("FOUNDRY_ENDPOINT", "https://myres.openai.azure.com/")

    def boom(req, timeout):
        raise OSError("down")
    monkeypatch.setattr(speech.urllib.request, "urlopen", boom)
    r = client.get("/speech/token")
    assert r.status_code == 502 and "k" != r.json()["error"]


def test_token_needs_the_access_key(client, monkeypatch):
    monkeypatch.setenv("TAI_ACCESS_KEY", "secret")
    assert client.get("/speech/token").status_code == 401
