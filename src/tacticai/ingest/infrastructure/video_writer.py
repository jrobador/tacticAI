"""ffmpeg/ffprobe wrappers (external tools, run via subprocess)."""
import functools
import os
import subprocess
import sys


@functools.lru_cache(maxsize=None)
def _has_atomic_writing():
    """Whether this ffmpeg's image2 muxer has -atomic_writing (checked once per process)."""
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-h", "muxer=image2"], capture_output=True, text=True)
    except OSError:
        return False
    return "atomic_writing" in r.stdout + r.stderr


class VideoWriter:
    def __init__(self, path, w, h, fps=10, preview_path=None):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt",
               "yuv420p", "-crf", "18", path]
        if preview_path and not (os.path.isdir(os.path.dirname(os.path.abspath(preview_path)))
                                 and os.access(os.path.dirname(os.path.abspath(preview_path)), os.W_OK)):
            print(f"warning: preview folder of {preview_path} is not writable, recording without preview", file=sys.stderr)
            preview_path = None
        if preview_path:  # second output: the latest frame as a small JPEG, overwritten in place
            cmd += ["-vf", "fps=5,scale=640:-2", "-q:v", "5", "-f", "image2", "-update", "1"]
            cmd += ["-atomic_writing", "1"] if _has_atomic_writing() else []
            cmd.append(preview_path)
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, bgr_bytes):
        self.proc.stdin.write(bgr_bytes)

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait():
            raise RuntimeError("ffmpeg failed")


def count_frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path],
                       capture_output=True, text=True, check=True)
    return int(r.stdout.strip())
