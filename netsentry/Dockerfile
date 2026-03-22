# ── Stage 1: Python dependencies ──────────────────────────────────────────────
FROM python:3.12-slim AS deps

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv==0.4.29

WORKDIR /app

# Copy dependency spec first (layer cache optimisation)
COPY pyproject.toml ./

# Install production dependencies only (no dev extras)
RUN uv pip install --system --no-cache ".[ai]" || uv pip install --system --no-cache .

# ── Stage 2: Node frontend build ───────────────────────────────────────────────
FROM node:20-slim AS frontend

WORKDIR /frontend

# Copy frontend package files
COPY frontend/package.json frontend/pnpm-lock.yaml* ./

# Install pnpm and dependencies
RUN npm install -g pnpm@9 && \
    pnpm install --frozen-lockfile 2>/dev/null || echo "No frontend lock file yet — skipping"

# Copy frontend source and build
COPY frontend/ ./
RUN pnpm build 2>/dev/null || mkdir -p dist && echo '{"status":"frontend-not-built"}' > dist/index.html

# ── Stage 3: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install system-level network scanning tools + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    arp-scan \
    fping \
    nbtscan \
    iputils-ping \
    curl \
    libpcap0.8 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with UID 1000
RUN useradd --uid 1000 --gid 0 --create-home --shell /bin/bash netsentry

WORKDIR /app

# Copy installed Python packages from deps stage
COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application source
COPY --chown=netsentry:root . /app

# Copy frontend build artifact
COPY --from=frontend --chown=netsentry:root /frontend/dist /app/frontend/dist

# Copy Alembic config
COPY alembic.ini /app/alembic.ini

# Create required directories with correct ownership
RUN mkdir -p /data /config && chown -R netsentry:root /data /config /app

# Switch to non-root user
USER netsentry

# Expose API port (informational — actual binding via network_mode: host)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=20s \
    CMD curl -f http://localhost:8080/api/v1/system/health || exit 1

# Entrypoint: run Alembic migrations then start uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn netsentry.api.main:create_app --factory --host 0.0.0.0 --port 8080 --log-level info"]
