# Server container targets:
# - default final stage (`dev`) runs FastAPI for local containerized backend runtime
# - `smoke` target uses the same boot path for container smoke testing via /health

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

COPY server/pyproject.toml server/uv.lock ./server/
RUN uv sync --project server --frozen --no-dev --no-install-project

COPY server ./server

FROM base AS dev

EXPOSE 8000

CMD ["uv", "run", "--project", "server", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM dev AS smoke
