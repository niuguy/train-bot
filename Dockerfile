# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Pre-copy dependency manifests to leverage Docker layer caching
COPY pyproject.toml uv.lock requirements.txt ./

RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

RUN uv sync --frozen --no-dev

# Copy application source
COPY src ./src

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "-m", "train_bot"]
