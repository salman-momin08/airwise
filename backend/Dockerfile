# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 airwise \
    && useradd --uid 10001 --gid airwise --shell /bin/bash --create-home airwise

WORKDIR /srv/airwise

COPY --from=builder /opt/venv /opt/venv
COPY --chown=airwise:airwise app ./app
COPY --chown=airwise:airwise alembic ./alembic
COPY --chown=airwise:airwise alembic.ini ./alembic.ini
COPY --chown=airwise:airwise scripts ./scripts

RUN mkdir -p /srv/airwise/alembic/versions && chown -R airwise:airwise /srv/airwise/alembic

USER airwise

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
