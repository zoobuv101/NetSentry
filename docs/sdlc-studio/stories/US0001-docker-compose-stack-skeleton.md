# US0001: Docker Compose Stack Skeleton

> **Status:** Ready
> **Epic:** [EP0001: Foundation — Docker Stack, Scanner Engine & Device Inventory](../epics/EP0001-foundation-scanner-inventory.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** a single `docker compose up -d` command to start the entire NetSentry stack
**So that** I can have the system running on my home server in under 5 minutes with no manual setup beyond configuring a `.env` file

## Context

### Background
This is the first story in the project. It establishes the Docker Compose topology: the main `netsentry` application container (host networking, `CAP_NET_RAW`), the `ntfy` notification container, and stub entries for optional `redis` and `librespeed` containers. No application code runs yet — the containers start, pass health checks, and shut down cleanly. This forms the skeleton every other story builds on.

---

## Inherited Constraints

| Source | Type | Constraint | AC Implication |
|--------|------|------------|----------------|
| TRD | Security | Container runs as UID 1000 non-root; `CAP_NET_RAW` only | Dockerfile must set `USER 1000`; compose must use `cap_add: [NET_RAW]` and `cap_drop: [ALL]` |
| TRD | Infrastructure | `network_mode: host` required for scanner container | `netsentry` service must use `network_mode: host` |
| PRD | Performance | Stack healthy within 60s of startup | Health check endpoint must respond within 60s |
| TRD ADR-003 | Deployment | FastAPI serves React build via StaticFiles | Single container for API + frontend |

---

## Acceptance Criteria

### AC1: Stack starts from clean clone
- **Given** a host with Docker Engine and Docker Compose v2 installed, and a `.env` file with valid placeholder values
- **When** `docker compose up -d` is run from the project root
- **Then** all services reach `healthy` or `running` state within 60 seconds, with no errors in `docker compose logs`

### AC2: netsentry container runs as non-root with correct capabilities
- **Given** the `netsentry` container is running
- **When** `docker compose exec netsentry id` is run
- **Then** output shows `uid=1000(netsentry) gid=1000(netsentry)`
- **And** `docker compose exec netsentry cat /proc/1/status | grep CapEff` shows `CAP_NET_RAW` and no other elevated capabilities

### AC3: Health check endpoint responds
- **Given** the `netsentry` container is running
- **When** `GET http://localhost:8080/api/v1/system/health` is called
- **Then** HTTP 200 is returned with body `{"status": "ok", "version": "<semver>"}` within 5 seconds

### AC4: ntfy container is reachable from netsentry
- **Given** both containers are running
- **When** `docker compose exec netsentry curl -s http://ntfy:80/health` is called
- **Then** a 200 response is returned (ntfy health check)

### AC5: Graceful shutdown
- **Given** the stack is running
- **When** `docker compose down` is run
- **Then** all containers stop within 30 seconds and no data corruption occurs on the SQLite volume

### AC6: Environment variable validation at startup
- **Given** a `.env` file with a required variable missing (e.g., `DECO_HOST` not set)
- **When** `docker compose up` is run
- **Then** the `netsentry` container starts with a logged warning (not a fatal error) since integrations are individually optional

### AC7: SQLite volume persists across restart
- **Given** the stack has run and created `/data/netsentry.db`
- **When** `docker compose restart netsentry` is run
- **Then** the database file is still present and unchanged after restart

---

## Scope

### In Scope
- `docker-compose.yml` with `netsentry`, `ntfy`, optional `redis`, optional `librespeed` services
- `docker-compose.dev.yml` override with hot-reload, dev ports
- `Dockerfile` for `netsentry`: Python 3.12 slim base, system packages (nmap, arp-scan, fping, nbtscan), Python deps via `uv`, non-root user, `CAP_NET_RAW`
- `.env.example` with all required and optional variables
- Minimal FastAPI app entrypoint serving `GET /api/v1/system/health`
- Docker named volumes: `netsentry-data` (SQLite), `netsentry-config` (secrets/certs)
- `ntfy` service with basic config

### Out of Scope
- Application logic, scanner, database schema (US0002+)
- Frontend (US0008)
- Actual integration credentials validation

---

## Technical Notes

### Dockerfile structure (multi-stage)
```dockerfile
FROM python:3.12-slim AS base
RUN apt-get install -y nmap arp-scan fping nbtscan iputils-ping ...
RUN useradd -u 1000 -m netsentry
COPY --chown=netsentry:netsentry . /app
USER netsentry
RUN uv pip install -e .
```

### docker-compose.yml key fields for netsentry service
```yaml
netsentry:
  network_mode: host
  cap_add: [NET_RAW]
  cap_drop: [ALL]
  user: "1000:1000"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/api/v1/system/health"]
    interval: 10s
    timeout: 5s
    retries: 6
  volumes:
    - netsentry-data:/data
    - netsentry-config:/config
```

### API Contracts
`GET /api/v1/system/health` → `200 {"status": "ok", "version": "0.1.0"}`

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Port 8080 already in use on host | `docker compose up` fails with clear port conflict error in logs |
| SQLite volume directory not writable by UID 1000 | Container logs error and exits with non-zero; health check fails |
| ntfy container fails to start | `netsentry` starts anyway; health check still returns 200 (ntfy is not a hard dependency at health check time) |
| `.env` file missing entirely | `docker compose up` fails with compose validation error listing missing required variables |
| Docker host is macOS/Windows (no `network_mode: host`) | Compose detects incompatibility; documentation notes macvlan alternative |
| Container killed mid-write to SQLite | WAL mode ensures no corruption; next startup continues normally |

---

## Test Scenarios (TDD)

- [ ] `test_health_endpoint_returns_200` — GET /api/v1/system/health returns 200 with correct body shape
- [ ] `test_health_endpoint_includes_version` — version field is a valid semver string
- [ ] `test_container_user_is_1000` — process runs as UID 1000
- [ ] `test_sqlite_volume_survives_restart` — file persists after container restart
- [ ] `test_ntfy_reachable_from_netsentry_network` — ntfy health endpoint accessible
- [ ] `test_graceful_shutdown_no_corruption` — SIGTERM handled; DB not corrupted

---

## Dependencies

### Story Dependencies
None — this is the first story.

### External Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| Docker Engine ≥ 24 + Compose v2 on host | Infrastructure | Operator responsibility |
| Python 3.12 slim base image available | Registry | Available |

---

## Estimation
**Story Points:** 3
**Complexity:** Low — infrastructure configuration, no business logic

---

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |
