FROM tai-engine
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
# The reels draw the player faces and the logo from the UI's public folder (found walking up from the package).
COPY ui/public/players /app/ui/public/players
COPY ui/public/tacticai-logo-dark-bg.png /app/ui/public/tacticai-logo-dark-bg.png
# Ubuntu 22.04's pip 22.0 builds this pyproject as "UNKNOWN" with no dependencies; a current pip reads [project].
RUN pip3 install --no-cache-dir -U pip setuptools && pip3 install --no-cache-dir "/app[agents]"
ENV PYTHONPATH=/app/src:/engine TAI_OUTPUT_DIR=/data
WORKDIR /app
