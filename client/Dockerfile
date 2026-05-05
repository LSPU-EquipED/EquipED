# Scaffold-only Vite container.
FROM node:20-slim

WORKDIR /app

RUN corepack enable

COPY client/ /app/

EXPOSE 5173

CMD ["sh", "-c", "echo 'Scaffold only (client container)'; sleep infinity"]
