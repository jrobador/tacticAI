import subprocess

from tacticai.ingest.application import generate_match as gm
from tacticai.ingest.infrastructure import video_writer as vw

BASE = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "4x2", "-r", "10", "-i", "-",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "v.mp4"]


def command(monkeypatch, atomic, **kw):
    seen = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **k: seen.append(cmd))
    monkeypatch.setattr(vw, "_has_atomic_writing", lambda: atomic)
    vw.VideoWriter("v.mp4", 4, 2, **kw)
    return seen[0]


def test_command_without_preview_is_unchanged(monkeypatch):
    assert command(monkeypatch, True) == BASE


def test_preview_is_a_second_output_after_the_video(monkeypatch, tmp_path):
    cmd = command(monkeypatch, True, preview_path=str(tmp_path / "p.jpg"))
    assert cmd[:len(BASE)] == BASE
    assert cmd[len(BASE):] == ["-vf", "fps=5,scale=640:-2", "-q:v", "5", "-f", "image2", "-update", "1",
                               "-atomic_writing", "1", str(tmp_path / "p.jpg")]


def test_preview_without_atomic_writing_support(monkeypatch, tmp_path):
    assert "-atomic_writing" not in command(monkeypatch, False, preview_path=str(tmp_path / "p.jpg"))


def test_atomic_writing_detection_is_cached(monkeypatch):
    calls = []
    out = type("R", (), {"stdout": "  -atomic_writing <boolean>", "stderr": ""})()
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or out)
    vw._has_atomic_writing.cache_clear()
    assert vw._has_atomic_writing() and vw._has_atomic_writing() and len(calls) == 1
    vw._has_atomic_writing.cache_clear()


def test_simulate_passes_preview_path_only_when_set(monkeypatch, tmp_path):
    made = []

    class Video:
        proc = type("P", (), {"poll": lambda self: 0})()
        def __init__(self, *a, **kw): made.append(kw)
        def write(self, b): pass
        def close(self): pass

    class Dog:
        def __init__(self, *a): pass
        def start(self): pass
        def progress(self, *a): pass
        def stop(self): pass

    class Game:
        done = True
        def step(self):
            raise RuntimeError("stop")

    monkeypatch.setattr(gm, "VideoWriter", Video)
    monkeypatch.setattr(gm, "RenderWatchdog", Dog)
    for pp in ("p.jpg", None):
        try:
            gm._simulate(Game(), str(tmp_path), 0, 10, True, 60, 100, preview_path=pp)
        except RuntimeError:
            pass
    assert made == [{"preview_path": "p.jpg"}, {}]


def test_preview_in_a_missing_folder_records_without_preview(monkeypatch, tmp_path):
    assert command(monkeypatch, True, preview_path=str(tmp_path / "nope" / "p.jpg")) == BASE
