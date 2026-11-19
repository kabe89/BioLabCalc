# Multi-stage Dockerfile for BioLabCalc ELN & LIMS Server
# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml setup.py README.md LICENSE MANIFEST.in ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip build wheel \
    && pip wheel --no-cache-dir --wheel-dir /wheels ".[eln,gel]"

# Stage 2: Runtime
FROM python:3.11-slim AS runner

LABEL maintainer="BioLabCalc Contributors <https://github.com/kabe89/BioLabCalc>" \
      description="BioLabCalc State-of-the-Art Electronic Lab Notebook (ELN) & LIMS Server"

WORKDIR /app

# Create non-root user and persistent storage directory
RUN groupadd -g 10001 biolabcalc && \
    useradd -u 10001 -g biolabcalc -m -s /bin/bash biolabcalc && \
    mkdir -p /data && \
    chown -R biolabcalc:biolabcalc /data /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

USER biolabcalc

ENV BIOLABCALC_STORAGE_DIR=/data \
    BIOLABCALC_ENV=production \
    PYTHONUNBUFFERED=1

EXPOSE 8080

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

ENTRYPOINT ["biolabcalc", "eln", "--host", "0.0.0.0", "--port", "8080", "--quiet", "--no-browser"]
