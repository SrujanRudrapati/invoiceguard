# Hosted demo (Render free: 0.1 CPU / 512 MB). Replay mode only: recorded model responses
# (mocked), no API key. The demo DB is built at image build time so startup is instant.

# 1. Build the review app.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2. Python runtime.
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY data ./data
COPY runs/history.jsonl ./runs/history.jsonl
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist ./web/dist
# Process the 24 main-set docs with recorded responses into data/invoiceguard.sqlite3.
RUN python -m invoiceguard.process --system replay

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn invoiceguard.serve:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
