"""ffmpeg/ffprobe wrappers (external tools, run via subprocess)."""
import subprocess


class VideoWriter:
    def __init__(self, path, w, h, fps=10):
        self.proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                                      "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt",
                                      "yuv420p", "-crf", "18", path], stdin=subprocess.PIPE)

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
