"""Vertical 9:16 clips: the full horizontal video centered on a 1080x1920 canvas, title on top, text and rating below.
<match>/video.mp4 + explain + personalize + interpret/players.json -> <match>/render/clips/<insight_id>.mp4 and manifest.json."""
import json
import os
import shutil
import subprocess
import tempfile
import textwrap

from ...explain.domain import placeholders as P
from ...core.files import read_jsonl

MAX_CLIPS, AFTER_S, BEFORE_S, MAX_LEN_S, MIN_LEN_S = 5, 2.0, 3.0, 15.0, 1.0


def interval(t_s, show_t_s, video_s):
    end = min(video_s, show_t_s + AFTER_S)
    return max(0.0, t_s - BEFORE_S, end - MAX_LEN_S), end


def pick(insights):
    return sorted(insights, key=lambda i: (-i["importance"]["value"], i["show_t_s"], i["insight_id"]))[:MAX_CLIPS]


def _font():
    font = os.environ.get("TAI_FONT")
    if not font or not os.path.isfile(font):
        return ""
    return "fontfile=" + font.replace("\\", "/").replace(":", "\\:") + ":"


def filter_graph(font, has_rating):
    """Texts come from files (textfile=, expansion=none): quotes, colons, % and backslashes in them need no escaping."""
    def dt(name, size, y):
        return f"drawtext={font}textfile={name}:expansion=none:fontsize={size}:fontcolor=white:x=(w-text_w)/2:y={y}:line_spacing=12"
    g = ["scale=1080:-2", "pad=1080:1920:0:(oh-ih)/2:black", dt("title.txt", 64, 380), dt("text.txt", 40, 1330)]
    if has_rating:
        g.append(dt("rating.txt", 46, 1700))
    return ",".join(g)


def _render(video, out, start, end, title, text, rating):
    with tempfile.TemporaryDirectory() as tmp:
        for name, s, width in (("title.txt", title, 28), ("text.txt", text, 46), ("rating.txt", rating or "", 40)):
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
                f.write("\n".join(textwrap.wrap(s, width)))
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", os.path.abspath(video), "-t", f"{end - start:.3f}",
               "-vf", filter_graph(_font(), bool(rating)), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.abspath(out)]
        done = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or "ffmpeg failed").strip().splitlines()[-1][:300])


def run(match_dir, video=None):
    """-> warnings. Failures go to manifest.json `errors`, never raised."""
    video = video or os.path.join(match_dir, "video.mp4")
    out_dir = os.path.join(match_dir, "render", "clips")
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"clips": [], "errors": []}
    warnings = []

    def save():
        with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=1)
        return warnings

    insights = read_jsonl(os.path.join(match_dir, "explain", "insights.jsonl"))
    if not os.path.isfile(video):
        manifest["errors"].append({"insight_id": None, "message": "no video.mp4"})
    elif shutil.which("ffmpeg") is None:
        manifest["errors"].append({"insight_id": None, "message": "ffmpeg not found"})
    if manifest["errors"]:
        warnings.append(f"clips: {manifest['errors'][0]['message']}")
        return save()
    with open(os.path.join(match_dir, "meta.json"), encoding="utf-8") as f:
        v = json.load(f)["video"]
    video_s = v["frames"] / v["fps"]
    with open(os.path.join(match_dir, "personalize", "variants", "fan_en_neutral.json"), encoding="utf-8") as f:
        texts = json.load(f)["texts"]
    try:
        with open(os.path.join(match_dir, "interpret", "players.json"), encoding="utf-8") as f:
            ratings = {p["player_id"]: p.get("rating") or {} for p in json.load(f)["players"]}
        with open(os.path.join(match_dir, "roster.json"), encoding="utf-8") as f:
            names = {p["player_id"]: p["name"] for p in json.load(f)["players"]}
    except OSError:
        ratings, names = {}, {}
    for ins in pick(insights):
        iid = ins["insight_id"]
        start, end = interval(ins["t_s"], ins["show_t_s"], video_s)
        if end - start < MIN_LEN_S:
            manifest["errors"].append({"insight_id": iid, "message": f"interval too short ({end - start:.2f} s)"})
            warnings.append(f"clip {iid} skipped: interval too short")
            continue
        t = texts.get(iid)
        title, text = (t["title"], t["text"]) if t else (ins["text"]["fact"], ins["text"]["why"])
        title, text = P.resolve_text(title, ins["metrics"]), P.resolve_text(text, ins["metrics"])
        main = ins["players"][-1] if ins["players"] else None
        value = ratings.get(main, {}).get("value") if main else None
        rating = f"{names.get(main, main)}  {value:+.2f} goals added" if value is not None else None
        dest = os.path.join(out_dir, f"{iid}.mp4")
        try:
            _render(video, dest, start, end, title, text, rating)
            manifest["clips"].append({"insight_id": iid, "file": f"render/clips/{iid}.mp4", "start_s": round(start, 3), "end_s": round(end, 3)})
        except Exception as err:
            if os.path.exists(dest):
                os.remove(dest)
            manifest["errors"].append({"insight_id": iid, "message": str(err)})
            warnings.append(f"clip {iid} failed: {err}")
    return save()
