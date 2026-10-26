#!/bin/sh
# Added by the tacticAI project: live viewer. Serves the virtual display over noVNC on :6080, then runs the given command.
command -v x11vnc >/dev/null || { echo "viewer not installed: build with --build-arg WITH_VIEWER=1"; exit 2; }
Xvfb :99 -screen 0 1280x720x24 &
sleep 1
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -quiet &
websockify --web /usr/share/novnc 6080 localhost:5900 &
export DISPLAY=:99
exec "$@"
