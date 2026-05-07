# Client container targets:
# - default final stage (`dev`) runs Vite for local containerized development
# - `smoke` target builds the app and serves it via `vite preview` for smoke testing

FROM node:20-slim AS base

ENV PNPM_HOME=/pnpm
ENV PATH=${PNPM_HOME}:${PATH}

WORKDIR /app

RUN corepack enable

COPY client/package.json client/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY client/index.html ./
COPY client/components.json ./
COPY client/eslint.config.js ./
COPY client/tailwind.config.ts ./
COPY client/tsconfig.json ./
COPY client/vite.config.ts ./
COPY client/.prettierrc ./
COPY client/src ./src

FROM base AS dev

EXPOSE 5173

CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]

FROM base AS smoke

RUN pnpm build

EXPOSE 4173

CMD ["pnpm", "preview", "--host", "0.0.0.0", "--port", "4173"]
