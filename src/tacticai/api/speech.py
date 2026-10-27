"""Azure AI Speech: hands the browser a 10-minute auth token so the key never leaves the server."""
import os
import urllib.request
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/speech/token")
def speech_token():
    key, endpoint = os.environ.get("FOUNDRY_API_KEY"), os.environ.get("FOUNDRY_ENDPOINT")
    host = urlparse(endpoint or "").hostname
    if not key or not host:
        raise HTTPException(503, "Speech is not configured")
    req = urllib.request.Request(f"https://{host.split('.')[0]}.cognitiveservices.azure.com/sts/v1.0/issueToken",
                                 data=b"", method="POST", headers={"Ocp-Apim-Subscription-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            token = r.read().decode()
    except Exception as e:  # urllib errors can echo the URL, never the key
        raise HTTPException(502, f"Speech token request failed ({getattr(e, 'code', type(e).__name__)})")
    return {"token": token, "region": os.environ.get("SPEECH_REGION", "brazilsouth")}
