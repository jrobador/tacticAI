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


def test_broken_batch_does_not_break_later_batches(monkeypatch, tmp_path):
    class Breaks(FakeExecutor):
        def submit(self, fn, args):
            if args[1] == 10:  # first seed of batch 1: pool already broken
                raise BrokenProcessPool("boom")
            return super().submit(fn, args)

    monkeypatch.setattr(S, "SEEDS_PER_WORKER", 2)
    pools = []
    monkeypatch.setattr(Breaks, "__init__", lambda self, *a, **k: pools.append(a))
    monkeypatch.setattr(S, "ProcessPoolExecutor", Breaks)
    monkeypatch.setattr(S, "_try", fake_try)
    monkeypatch.setattr(S, "to_dict", lambda r: {})
    report = S.search(SimpleNamespace(seed=10, seeds=5, mode="free"), str(tmp_path), workers=1, render_winner=False)[1]
    assert len(pools) == 3
    assert [r.get("error") for r in report["results"]] == ["worker process died"] * 2 + [None] * 3


def stop_run(monkeypatch, tmp_path, wanted, seeds=12, ok=lambda seed: seed in (10, 13, 17)):
    monkeypatch.setattr(S, "SEEDS_PER_WORKER", 2)
    monkeypatch.setattr(S, "ProcessPoolExecutor", FakeExecutor)
    monkeypatch.setattr(S, "_try", lambda a: {"seed": a[1], "ok": ok(a[1]), "score": a[1]})
    monkeypatch.setattr(S, "to_dict", lambda r: {})
    calls = []
    recipe = SimpleNamespace(seed=10, seeds=seeds, mode="situation", situation=SimpleNamespace(wanted=wanted))
    report = S.search(recipe, str(tmp_path), workers=2, render_winner=False, on_progress=lambda d, t: calls.append((d, t)))[1]
    return report, calls


def test_stops_after_the_batch_with_the_third_winner(monkeypatch, tmp_path):
    report, calls = stop_run(monkeypatch, tmp_path, ["goal_by_team:home"])  # batches of 4: 10-13, 14-17 (3rd winner), 18-21
    assert report["stopped_early"] and report["seeds"] == list(range(10, 18))
    assert [r["seed"] for r in report["results"]] == list(range(10, 18)) and report["winner"] == 17
    assert calls[-1] == (8, 8)


def test_no_early_stop_with_ranking_entries_or_few_winners(monkeypatch, tmp_path):
    report, _ = stop_run(monkeypatch, tmp_path, ["goal_by_team:home", "more_pressure:home"], ok=lambda s: True)
    assert not report["stopped_early"] and len(report["results"]) == 12
    report, _ = stop_run(monkeypatch, tmp_path, ["goal_by_team:home"], ok=lambda s: s == 10)
    assert not report["stopped_early"] and len(report["results"]) == 12


def test_no_early_stop_without_a_boolean_filter(monkeypatch, tmp_path):
    for wanted in ([], ["more_possession:home"]):
        report, _ = stop_run(monkeypatch, tmp_path, wanted, ok=lambda s: True)
        assert not report["stopped_early"] and len(report["results"]) == 12
    monkeypatch.setattr(S, "ProcessPoolExecutor", FakeExecutor)
    monkeypatch.setattr(S, "_try", fake_try)
    monkeypatch.setattr(S, "to_dict", lambda r: {})
    full = SimpleNamespace(seed=10, seeds=30, mode="full_match", situation=None)  # 30 seeds > one batch of 20
    assert len(S.search(full, str(tmp_path), render_winner=False)[1]["results"]) == 30
