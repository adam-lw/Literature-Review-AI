# Dev container for the backend API. Project source is bind-mounted in by docker-compose.yml
# (not COPYed here), so code edits on the host are picked up without an image rebuild — only
# `docker compose restart api` is needed. The `.venv` lives in a named volume, keyed off
# pyproject.toml/uv.lock, so `uv sync` is a fast no-op after the first run.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

EXPOSE 8000

CMD ["sh", "-c", "uv sync --locked && exec uv run python main.py"]
