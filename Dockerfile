FROM python:3.12-alpine AS builder

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv

WORKDIR /app

# Warm up to avoid findpython timeout on arm64 build
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    /usr/local/bin/python -EsSc 'import platform; print(platform.python_version())' \
    && uv sync --locked --no-dev --no-install-project --no-editable

COPY pyproject.toml uv.lock README.md LICENSE /app/
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    CALIBRE_LIBRARY_PATH=/app/calibre/

WORKDIR /app

# Create a non-root user to run the application
RUN addgroup -S -g 1000 appuser && adduser -S -u 1000 -G appuser appuser

COPY --from=builder --chown=1000:1000 /app/.venv /app/.venv

# Switch to the non-root user
USER 1000:1000

EXPOSE 8000

CMD ["uvicorn", "opds_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
