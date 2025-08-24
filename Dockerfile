FROM python:3.12

ENV POETRY_VERSION=2.1.4 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

WORKDIR /app

COPY pyproject.toml poetry.lock* /app/

RUN poetry config virtualenvs.create false \
  && poetry install --only main --no-root --no-interaction --no-ansi

COPY src/ ./src/
ENV PYTHONPATH=/app/src \
    CALIBRE_LIBRARY_PATH=/app/calibre/

RUN useradd -u 10001 -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "opds_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
