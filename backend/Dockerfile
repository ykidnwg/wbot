FROM python:3.14-slim AS checks

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY tests ./tests

RUN --mount=type=cache,target=/root/.cache/pip pip install --upgrade pip==25.3 && pip install ".[dev]" \
    && ruff check app tests \
    && mypy app \
    && pytest \
    && touch /checks-passed

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY --from=checks /checks-passed /tmp/checks-passed

RUN --mount=type=cache,target=/root/.cache/pip pip install --upgrade pip==25.3 && pip install . && rm /tmp/checks-passed

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
