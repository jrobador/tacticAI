import os
import shutil
import time
from pathlib import Path

from tacticai.orchestration import pipeline
from tacticai.explain.application import build_insights as B
from tacticai.personalize.application import build_personalize, lens_agent, recap_agent
from tacticai.render.application import director_agent, plans

FIX = Path(__file__).parent.parent / "explain" / "fixtures" / "match"


def slow(result=None, error=None):
    def fake(*args):
        time.sleep(0.3)
        if error:
            raise error
        return {} if result is None else result
    return fake


def tree(root):
    return {os.path.relpath(os.path.join(d, f), root): open(os.path.join(d, f), "rb").read()
            for d, _, fs in os.walk(root) for f in fs if f.split(".")[0] != "manifest" and os.path.relpath(d, root).split(os.sep)[0] in ("personalize", "render")}


def enrich(tmp, name, monkeypatch, director_error=None):
    d = str(tmp / name)
    shutil.copytree(FIX, d)
    monkeypatch.setattr(pipeline, "explain_run", lambda m: B.run(m, context={}))
    monkeypatch.setattr(pipeline, "heatmaps_run", lambda m: None)
    monkeypatch.setattr(pipeline, "reels_run", lambda m, video=None: [])
    monkeypatch.setattr(pipeline, "rundown_run", lambda m: [])  # the fixture has no tracking.jsonl
    monkeypatch.setattr(lens_agent, "adapt_texts", slow())
    monkeypatch.setattr(recap_agent, "write_recaps", slow())
    monkeypatch.setattr(director_agent, "plan_all", slow(error=director_error))
    monkeypatch.setattr(B, "build_match_context", lambda m: {"ctx": 1})
    monkeypatch.setattr(pipeline, "build_match_context", lambda m: {"ctx": 1})
    monkeypatch.setattr(build_personalize, "build_match_context", lambda m: {"ctx": 1})
    monkeypatch.setattr(plans, "build_match_context", lambda m: {"ctx": 1})
    t = time.time()
    warnings = pipeline.enrich_steps(d, lambda s, p=None: None)
    return d, warnings, time.time() - t


def sequential(d):
    insights = B.run(d, context={})
    ctx = {"ctx": 1}
    w = build_personalize.run(d, context=ctx, lens_agent=slow(), recap_agent=slow())
    return w + plans.run(d, agent=slow(error=None), context=ctx)


def test_three_calls_run_together_and_match_the_sequential_result(tmp_path, monkeypatch):
    d, warnings, took = enrich(tmp_path, "par", monkeypatch)
    assert took < 0.7
    seq = str(tmp_path / "seq")
    shutil.copytree(FIX, seq)
    monkeypatch.setattr(pipeline, "explain_run", lambda m: B.run(m, context={}))
    w = sequential(seq)
    assert warnings == w and tree(d) == tree(seq)


def test_a_failing_director_gives_the_same_warning_and_rules_plans(tmp_path, monkeypatch):
    d, warnings, _ = enrich(tmp_path, "par", monkeypatch, director_error=RuntimeError("boom"))
    seq = str(tmp_path / "seq")
    shutil.copytree(FIX, seq)
    B.run(seq, context={})
    w = build_personalize.run(seq, context={"ctx": 1}, lens_agent=slow(), recap_agent=slow())
    w += plans.run(seq, agent=slow(error=RuntimeError("boom")), context={"ctx": 1})
    assert "render: director failed (boom); all plans from rules" in warnings
    assert warnings == w and tree(d) == tree(seq)
