"""Stage 1 — Ingest: synthetic match factory.

Responsibility: simulate a match with the tacticAI engine and publish, per match, the files other stages consume:
video.mp4, tracking.jsonl, roster.json, events.jsonl, events_summary.json and meta.json (see docs/ingest/engine-reference.md).
"""
