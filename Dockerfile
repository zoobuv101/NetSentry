# ── Stage 1: Python dependencies ──────────────────────────────────────────────
FROM python:3.12-slim AS deps

# Install build tools needed for C extension packages (netifaces, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv==0.4.29

WORKDIR /app

# hatchling (the build backend) requires README.md to build the package wheel
COPY pyproject.toml README.md ./

# Install production dependencies only (no dev extras)
# Try with AI extra (anthropic) first, fall back to base if not available
RUN uv pip install --system --no-cache ".[ai]" || uv pip install --system --no-cache .

# ── Stage 2: Node frontend build ───────────────────────────────────────────────
FROM node:20-slim AS frontend

WORKDIR /frontend

# Copy lockfile first for layer cache — dependencies only reinstall on lockfile change
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# Install pnpm and project dependencies
RUN npm install -g pnpm@9 && pnpm install --frozen-lockfile

# Copy full frontend source and build
# This runs after deps install so source changes don't invalidate the dep cache
COPY frontend/ ./
RUN pnpm build

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
    speedtest-cli \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with UID 1000
RUN useradd --uid 1000 --gid 0 --create-home --shell /bin/bash netsentry

WORKDIR /app

# Copy installed Python packages from deps stage
COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application source
COPY --chown=netsentry:root . /app

# Copy compiled frontend from frontend stage
# This will fail the build if pnpm build failed — no silent fallback
COPY --from=frontend --chown=netsentry:root /frontend/dist /app/frontend/dist

# Copy Alembic config
COPY alembic.ini /app/alembic.ini

# Allow netsentry (UID 1000) to run network scanning tools without password.
# NET_RAW capability alone is insufficient — arp-scan and nmap need root
# or explicit sudo permission to send raw packets.
RUN apt-get update && apt-get install -y --no-install-recommends sudo && \
    rm -rf /var/lib/apt/lists/* && \
    echo "netsentry ALL=(root) NOPASSWD: /usr/sbin/arp-scan, /usr/bin/nmap, /usr/bin/fping, /usr/sbin/nbtscan" \
    >> /etc/sudoers.d/netsentry && \
    chmod 0440 /etc/sudoers.d/netsentry

# Create data and config directories with correct ownership
RUN mkdir -p /data /config /app/data && chown -R netsentry:root /data /config /app

# Download Wireshark OUI vendor database for device identification
# Try GitHub mirror first (more reliable), fall back to bundled minimal database
RUN curl -fsSL --max-time 30 \
    "https://raw.githubusercontent.com/boundary/wireshark/master/manuf" \
    -o /app/data/manuf 2>/dev/null && \
    echo "OUI database downloaded: $(grep -c '^[0-9A-Fa-f]' /app/data/manuf) entries" || \
    (echo "WARNING: OUI download failed — using bundled vendor list" && \
     cp /app/netsentry/data/manuf /app/data/manuf)

# Switch to non-root user
USER netsentry

# Expose API port (informational — actual binding via network_mode: host in compose)
EXPOSE 8282

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=30s \
    CMD curl -f http://localhost:8282/api/v1/system/health || exit 1

# Run Alembic migrations then start uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn netsentry.api.main:create_app --factory --host 0.0.0.0 --port 8282 --log-level info"]
