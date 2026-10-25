FROM python:3.12-alpine

ENV UV_VERSION=0.13.5 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir "uv==$UV_VERSION"

WORKDIR /app

COPY pyproject.toml uv.lock /app/

# Warm up to avoid findpython timeout on arm64 build
RUN /usr/local/bin/python -EsSc 'import platform; print(platform.python_version())'

RUN UV_PROJECT_ENVIRONMENT=/usr/local uv sync --locked --no-dev --no-install-project --inexact

COPY src/ ./src/
ENV PYTHONPATH=/app/src \
    CALIBRE_LIBRARY_PATH=/app/calibre/

# Create a non-root user to run the application
RUN addgroup -S -g 1000 appuser && adduser -S -u 1000 -G appuser appuser

# Switch to the non-root user
USER appuser

EXPOSE 8000

CMD ["uvicorn", "opds_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
