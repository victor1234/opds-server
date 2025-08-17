FROM python:3.13-slim

ENV POETRY_VERSION=2.1.4
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app
COPY pyproject.toml poetry.lock* /app/
RUN poetry config virtualenvs.create false \
  && poetry install --no-root --no-interaction --no-ansi

COPY src/ /app/src/
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "opds_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
