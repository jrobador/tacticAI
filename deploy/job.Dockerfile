FROM tai-engine
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
RUN pip3 install --no-cache-dir "/app[agents]"
ENV PYTHONPATH=/app/src:/engine TAI_OUTPUT_DIR=/data
WORKDIR /app
