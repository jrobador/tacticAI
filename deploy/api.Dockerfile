FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY ui/dist /app/ui/dist
RUN pip install --no-cache-dir ".[api,agents]"
# app.py looks for the UI at <root>/ui/dist relative to src/tacticai/api, so the code runs from /app/src (not site-packages)
ENV PYTHONPATH=/app/src TAI_OUTPUT_DIR=/data TAI_RUNNER=aca
EXPOSE 8000
CMD ["uvicorn", "tacticai.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
