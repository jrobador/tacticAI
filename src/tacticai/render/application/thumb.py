"""render/thumb.jpg: a 640 px wide frame of video.mp4 at the match's most important moment (mid-video when there are no insights)."""
import json
import os
import shutil
import subprocess

from ...core.files import read_jsonl


def moment_s(match_dir):
    path = os.path.join(match_dir, "explain", "insights.jsonl")
    insights = read_jsonl(path) if os.path.isfile(path) else []
    if insights:
        return max(insights, key=lambda i: (i["importance"]["value"], -i["t_s"]))["t_s"]
    with open(os.path.join(match_dir, "meta.json"), encoding="utf-8") as f:
        v = json.load(f)["video"]
    return v["frames"] / v["fps"] / 2


def run(match_dir, video=None):
    """-> warnings. A failure is a warning, never raised; no video.mp4 is not one (reels reports it)."""
    video = video or os.path.join(match_dir, "video.mp4")
    try:
        if not os.path.isfile(video):
            return []  # reels already warns about a missing video
        if shutil.which("ffmpeg") is None:
            return ["thumb: ffmpeg not found"]
        out = os.path.join(match_dir, "render", "thumb.jpg")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{moment_s(match_dir):.3f}", "-i", os.path.abspath(video),
               "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", os.path.abspath(out)]
        done = subprocess.run(cmd, capture_output=True, text=True)
        if done.returncode != 0 or not os.path.isfile(out):
            return [f"thumb failed: {(done.stderr or 'ffmpeg failed').strip().splitlines()[-1][:300]}"]
        return []
    except Exception as err:
        return [f"thumb failed: {err}"]
