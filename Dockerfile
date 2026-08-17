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

# torch ships CPU-only by default (see the "cpu"/"cuda" extras in pyproject.toml) so the
# multi-GB NVIDIA CUDA toolkit is never downloaded unless this container actually has a GPU
# passed through to it (e.g. via `--gpus all` / the nvidia-container-toolkit runtime).
CMD if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then \
        gpu_extra=cuda; \
    else \
        gpu_extra=cpu; \
    fi; \
    echo "Installing torch extra: $gpu_extra"; \
    uv sync --locked --extra "$gpu_extra" && exec uv run python main.py
