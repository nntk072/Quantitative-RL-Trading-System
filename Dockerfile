FROM python:3.12-slim AS builder

ARG TORCH_DEVICE=cpu

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    g++ \
    && rm -rf /var/lib/apt/lists/*

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

RUN pip install uv

WORKDIR /build

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

RUN groupadd -g 1001 appgroup && useradd -u 1001 -g appgroup -m -d /app appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder --chown=1001:1001 /build /app
COPY --from=builder --chown=1001:1001 /build/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

USER 1001

ENTRYPOINT ["python"]

FROM runtime AS dev

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv
USER 1001

FROM runtime AS test

USER root
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*
RUN uv sync --frozen --extra dev \
    && chown -R 1001:1001 /app/.venv
USER 1001
ENTRYPOINT ["python", "-m", "pytest"]
