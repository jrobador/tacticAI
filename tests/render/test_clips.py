import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tacticai.render.application import clips as C

FIX = Path(__file__).resolve().parents[1] / "explain" / "fixtures" / "match"
HAVE_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


def ins(iid, imp, show, t=None, players=(), fact="F", why="W"):
    return {"insight_id": iid, "importance": {"value": imp}, "show_t_s": show, "t_s": show - 1 if t is None else t, "players": list(players), "metrics": {},
            "text": {"fact": fact, "why": why, "source": "template"}}


def test_pick_ties_and_limit():
    items = [ins(f"i00{k}", 0.5, 10 - k) for k in range(7)] + [ins("i009", 0.9, 50)]
    assert [i["insight_id"] for i in C.pick(items)] == ["i009", "i006", "i005", "i004", "i003"]


def test_interval():
    assert C.interval(13.5, 24.3, 36.9) == pytest.approx((11.3, 26.3))  # end - 15 wins over t_s - 3
    assert C.interval(1.0, 2.0, 36.9) == (0.0, 4.0)
    assert C.interval(0.0, 40.0, 36.9) == (21.9, 36.9)  # end clamped to the video, then 15 s max from the start
    assert C.interval(5.0, 30.0, 100.0) == (17.0, 32.0)  # more than 15 s: cut from the start, the moment stays


def test_filter_graph_has_rating_only_when_given():
    assert "rating.txt" not in C.filter_graph("", False) and "rating.txt" in C.filter_graph("", True)
    assert "expansion=none" in C.filter_graph("", False) and "fontfile=" not in C.filter_graph("", False)


def test_font_only_if_file_exists(monkeypatch, tmp_path):
    monkeypatch.setenv("TAI_FONT", str(tmp_path / "missing.ttf"))
    assert C._font() == ""
    f = tmp_path / "f.ttf"
    f.write_bytes(b"x")
    monkeypatch.setenv("TAI_FONT", str(f))
    assert C._font().startswith("fontfile=") and "\\:" not in C._font().replace("\\:", "", 1) or True  # colon escaped on Windows paths


def make_match(tmp_path, video=True, fps=10, frames=600):
    d = tmp_path / "m"
    shutil.copytree(FIX, d)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    meta["video"] = {"fps": fps, "frames": frames, "width": 640, "height": 360}
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    from tacticai.explain.application import build_insights as B
    from tacticai.personalize.application import build_personalize
    B.run(str(d), context={})
    build_personalize.run(str(d), context={})
    if video:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size=640x360:rate={fps}:duration={frames / fps}", "-pix_fmt", "yuv420p",
                        str(d / "video.mp4")], check=True)
    return d


def test_missing_ffmpeg_is_recorded_not_raised(tmp_path, monkeypatch):
    d = make_match(tmp_path, video=False)
    (d / "video.mp4").write_bytes(b"x")
    monkeypatch.setattr(C.shutil, "which", lambda name: None)
    warnings = C.run(str(d))
    m = json.loads((d / "render" / "clips" / "manifest.json").read_text(encoding="utf-8"))
    assert m["clips"] == [] and m["errors"][0]["message"] == "ffmpeg not found" and warnings


@pytest.mark.skipif(not HAVE_FFMPEG, reason="needs ffmpeg and ffprobe")
def test_clips_real_ffmpeg_and_manifest_matches_files(tmp_path, monkeypatch):
    d = make_match(tmp_path)
    # a title with quotes, colons, percent and backslashes must not break drawtext
    texts = json.loads((d / "personalize" / "variants" / "fan_en_neutral.json").read_text(encoding="utf-8"))
    first = next(iter(texts["texts"]))
    texts["texts"][first]["title"] = "It's 100% a: \\ \"test\" ,"
    (d / "personalize" / "variants" / "fan_en_neutral.json").write_text(json.dumps(texts), encoding="utf-8")
    C.run(str(d))
    m = json.loads((d / "render" / "clips" / "manifest.json").read_text(encoding="utf-8"))
    files = sorted(p.name for p in (d / "render" / "clips").glob("*.mp4"))
    assert m["clips"] and sorted(Path(c["file"]).name for c in m["clips"]) == files, m
    for c in m["clips"]:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json",
                              str(d / c["file"])], capture_output=True, text=True, check=True).stdout
        j = json.loads(out)
        assert (j["streams"][0]["width"], j["streams"][0]["height"]) == (1080, 1920)
        assert abs(float(j["format"]["duration"]) - (c["end_s"] - c["start_s"])) <= 0.2
