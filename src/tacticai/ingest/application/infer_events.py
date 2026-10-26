import os

from ..domain.events import DEFAULTS, extract, summarize
from ...core.files import read_json, read_jsonl, write_json, write_jsonl


def infer_events(match_dir, th=None):
    th = th or dict(DEFAULTS)
    rows = read_jsonl(os.path.join(match_dir, "tracking.jsonl"))
    ev = extract(rows, th, read_json(os.path.join(match_dir, "meta.json"))["pitch"]["length_m"])
    write_jsonl(os.path.join(match_dir, "events.jsonl"), ev)
    s = summarize(ev, len(rows), th)
    write_json(os.path.join(match_dir, "events_summary.json"), s)
    return s
