"""Hard-exit watchdog: a C call blocked in the renderer cannot be interrupted from Python."""
import os
import sys
import threading
import time


class RenderWatchdog:
    def __init__(self, timeout, out_dir):
        self.timeout, self.out_dir = timeout, out_dir
        self.last = time.monotonic()
        self.step = self.frame_index = 0
        self.done = threading.Event()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def progress(self, step, frame_index):
        self.step, self.frame_index, self.last = step, frame_index, time.monotonic()

    def stop(self):
        self.done.set()

    def _run(self):
        while not self.done.wait(1):
            if time.monotonic() - self.last > self.timeout:
                sys.stderr.write(f"ERROR: render stalled: no engine frame for {self.timeout}s at step {self.step}, "
                                 f"frame {self.frame_index}. Outputs in {self.out_dir} are incomplete.\n")
                sys.stderr.flush()
                os._exit(3)
