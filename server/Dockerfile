# Scaffold-only FastAPI container.
FROM python:3.12-slim

WORKDIR /app

COPY server/ /app/

EXPOSE 8000

CMD ["sh", "-c", "echo 'Scaffold only (server container)'; sleep infinity"]
