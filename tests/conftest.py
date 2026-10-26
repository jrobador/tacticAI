import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def _no_foundry(request, monkeypatch):
    """Offline tests never see FOUNDRY_* (a live eval's load_dotenv would leak it); *_eval.py files keep it."""
    if not request.node.path.name.endswith("_eval.py"):
        for v in ("FOUNDRY_ENDPOINT", "FOUNDRY_DEPLOYMENT", "FOUNDRY_API_KEY"):
            monkeypatch.delenv(v, raising=False)
