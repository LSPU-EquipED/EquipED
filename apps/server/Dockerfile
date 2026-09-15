# Server container targets:
# - `dev` target runs FastAPI with reload for local development
# - `prod` target runs FastAPI without reload (1 worker per EquipED single-process contract)
# - `smoke` target boots backend and exposes /health for smoke tests

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

# Install Tesseract OCR and required language packs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fil \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.7.22 /uv /uvx /bin/

COPY apps/server/pyproject.toml apps/server/uv.lock ./apps/server/
RUN uv sync --project apps/server --frozen --no-dev --no-install-project

COPY apps/server ./apps/server

# Development target: runs uvicorn server.main:app with hot reload
FROM base AS dev

WORKDIR /app/apps

EXPOSE 8000

CMD ["uv", "run", "--project", "server", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Smoke target for local container validation
FROM dev AS smoke

# Production target: runs uvicorn server.main:app without reload (single worker)
FROM base AS prod

WORKDIR /app/apps

EXPOSE 8000

CMD ["uv", "run", "--project", "server", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
