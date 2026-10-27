import json
import shutil
import subprocess

import pytest

from tacticai.render.application import thumb as T

HAVE_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


def make_match(tmp_path, fps=10, frames=100):
    d = tmp_path / "m"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"video": {"fps": fps, "frames": frames}}), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size=640x360:rate={fps}:duration={frames / fps}", "-pix_fmt", "yuv420p",
                    str(d / "video.mp4")], check=True)
    return d


def test_moment_is_the_most_important_insight(tmp_path):
    d = tmp_path
    (d / "explain").mkdir()
    rows = [{"insight_id": "i000", "t_s": 3.0, "importance": {"value": 0.4}}, {"insight_id": "i001", "t_s": 7.5, "importance": {"value": 0.9}}]
    (d / "explain" / "insights.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert T.moment_s(str(d)) == 7.5


def test_moment_falls_back_to_mid_video(tmp_path):
    (tmp_path / "meta.json").write_text(json.dumps({"video": {"fps": 10, "frames": 200}}), encoding="utf-8")
    assert T.moment_s(str(tmp_path)) == 10.0


def test_missing_video_or_ffmpeg_is_a_warning(tmp_path, monkeypatch):
    assert T.run(str(tmp_path)) == []
    (tmp_path / "video.mp4").write_bytes(b"x")
    monkeypatch.setattr(T.shutil, "which", lambda name: None)
    assert T.run(str(tmp_path)) == ["thumb: ffmpeg not found"]


@pytest.mark.skipif(not HAVE_FFMPEG, reason="needs ffmpeg and ffprobe")
def test_thumb_real_ffmpeg_is_640_wide(tmp_path):
    d = make_match(tmp_path)
    assert T.run(str(d)) == []
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(d / "render" / "thumb.jpg")],
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out)["streams"][0]["width"] == 640
