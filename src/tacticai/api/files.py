"""Safe file resolver: fixed file lists, id regexes and a path that must stay inside matches/ or library/."""
import os
import re

from ..orchestration import jobs
from ..orchestration.library import library_dir

MATCH_FILES = ("meta.json", "roster.json", "events.jsonl", "tracking.jsonl", "video.mp4", "interpret/meta.json",
               "interpret/events_enriched.jsonl", "interpret/sequences.jsonl", "interpret/timeline.jsonl",
               "interpret/players.json", "interpret/teams.json", "interpret/quality.json",
               "interpret/tactical_notes.jsonl", "interpret/phases.jsonl", "interpret/agents.json")
_V = r"(analyst|fan|first_match)_(en|es)_(neutral|home|away)"
_P = r"(analyst|fan|first_match|broadcast)_(neutral|home|away)"
MATCH_PATTERNS = (r"explain/insights\.jsonl", r"explain/meta\.json", rf"personalize/variants/{_V}\.json", rf"personalize/recaps/{_V}\.json",
                  rf"render/plans/{_P}\.json", r"render/heatmaps\.json", r"render/clips/manifest\.json", r"render/clips/i\d{3}\.mp4")
LIBRARY_FILES = tuple(f for f in MATCH_FILES if f != "video.mp4") + ("recipe.json",)
ENTRY_ID_RE = re.compile(r"^[a-z_]+-(home|away)-(goal|shot)-\d{2}$")
MEDIA = {".json": "application/json", ".jsonl": "application/x-ndjson", ".mp4": "video/mp4"}


def roots():
    return {"matches": os.path.abspath(os.path.join(jobs.data_dir(), "matches")), "library": library_dir()}


def resolve(kind, ident, name):
    """Absolute path of a served file of a match ("matches") or a library entry ("library"), else None."""
    id_re, allowed = (jobs.JOB_ID_RE, MATCH_FILES) if kind == "matches" else (ENTRY_ID_RE, LIBRARY_FILES)
    ok = name in allowed or (kind == "matches" and any(re.fullmatch(p, name) for p in MATCH_PATTERNS))
    if not id_re.match(ident) or not ok:
        return None
    root = os.path.realpath(roots()[kind])
    path = os.path.realpath(os.path.join(root, ident, name))
    if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
        return None
    return path
