FROM ghcr.io/astral-sh/uv:0.12.0 AS uv
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    APP_ENV=production \
    CHUNK_STORE_PATH=/app/data/processed/documents.sqlite3

WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend ./backend
COPY frontend ./frontend
COPY data/raw/demo_pump_manual.md ./data/raw/demo_pump_manual.md
COPY data/demo/fault_history.json ./data/demo/fault_history.json
RUN useradd --uid 10001 --create-home copilot \
    && mkdir -p /app/data/processed \
    && chown -R copilot:copilot /app/data
USER copilot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:8000'+os.getenv('API_PREFIX','/api/v1').rstrip('/')+'/health',timeout=3)"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
