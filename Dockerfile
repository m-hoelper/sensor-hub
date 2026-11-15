FROM python:3.12-slim

# uv from its official image: same tool and same lock file as on the Mac
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# 1) dependencies only: this layer is cached until pyproject.toml / uv.lock change
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

# 2) the app itself (changes often → rebuilt in seconds)
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# bring the schema up to date, then serve; 0.0.0.0 so the ESP32 (and the host) can reach it
CMD ["sh", "-c", "alembic upgrade head && uvicorn sensor_hub.main:app --host 0.0.0.0 --port 8000"]
