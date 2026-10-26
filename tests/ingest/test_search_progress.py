from concurrent.futures import Future
from concurrent.futures.process import BrokenProcessPool
from types import SimpleNamespace

from tacticai.ingest.application import search as S


class FakeExecutor:
    dead = None  # seed whose worker "dies"

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, args):
        f = Future()
        if args[1] == self.dead:
            f.set_exception(BrokenProcessPool("boom"))
        else:
            f.set_result(fn(args))
        return f


def fake_try(args):
    _, seed = args
    return {"seed": seed, "ok": True, "score": seed % 3}


def run(monkeypatch, tmp_path, **kw):
    monkeypatch.setattr(S, "ProcessPoolExecutor", FakeExecutor)
    monkeypatch.setattr(S, "_try", fake_try)
    monkeypatch.setattr(S, "to_dict", lambda r: {})
    recipe = SimpleNamespace(seed=10, seeds=5, mode="free")
    return S.search(recipe, str(tmp_path), render_winner=False, **kw)[1]


def test_progress_counts_and_same_report(monkeypatch, tmp_path):
    calls = []
    plain = run(monkeypatch, tmp_path)
    report = run(monkeypatch, tmp_path, on_progress=lambda d, t: calls.append((d, t)))
    assert calls == [(i, 5) for i in range(1, 6)]
    assert [r["seed"] for r in report["results"]] == [10, 11, 12, 13, 14]
    plain.pop("elapsed_s"), report.pop("elapsed_s")
    assert report == plain


def test_dead_worker_becomes_error(monkeypatch, tmp_path):
    monkeypatch.setattr(FakeExecutor, "dead", 12)
    calls = []
    report = run(monkeypatch, tmp_path, on_progress=lambda d, t: calls.append(d))
    assert [r["seed"] for r in report["results"]] == [10, 11, 12, 13, 14]
    assert report["results"][2] == {"seed": 12, "error": "worker process died"}
    assert calls == [1, 2, 3, 4, 5]
    assert report["winner"] == 11
