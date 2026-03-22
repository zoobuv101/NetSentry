# EP0001: Foundation — Docker Stack, Scanner Engine & Device Inventory

> **Status:** Draft
> **Phase:** 1 — Local Scanning Foundation
> **Created:** 2026-03-21
> **PRD Reference:** [PRD](../prd.md) · [TRD](../trd.md)

## Summary

Establishes the entire NetSentry foundation: the Docker Compose stack, the Python backend skeleton, the SQLite database schema with Alembic migrations, the active local network scanner (ARP/ICMP/TCP/mDNS/SSDP/NetBIOS), the device inventory repository, the APScheduler task harness, and a minimal FastAPI REST API. This is the MVP — every subsequent epic builds on top of this one.

---

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| TRD ADR-001 | Architecture | Modular monolith; all modules in one Python process | No inter-service networking; direct function calls between modules |
| TRD ADR-002 | Data | SQLite + aiosqlite; Alembic migrations run at startup | Repository layer must be async throughout |
| PRD NFR | Performance | /24 ARP sweep <30s; standard scan <60s | Scanner must use parallel tools (arp-scan, fping, nmap) |
| TRD | Security | Container runs as non-root UID 1000; `CAP_NET_RAW` only for scanner | Dockerfile and compose must be explicit about capabilities |
| TRD | Infrastructure | `network_mode: host` required for ARP scanning | Scanner container has no bridge network isolation |

---

## Business Context

### Problem Statement
Without this epic nothing else can be built. The operator has no visibility into their home network today — they cannot see all devices, track when they joined, or be alerted to new arrivals.

**PRD Reference:** PRD §3 Feature Inventory — Local Network Scanning; Device Inventory & History

### Value Proposition
After this epic the operator has a running Docker Compose stack that continuously discovers every device on their network, stores a persistent enriched inventory, and exposes a REST API to query it. This is the minimum useful product.

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| ARP sweep coverage | 100% of devices visible to pfSense ARP table | Compare NetSentry inventory vs pfSense ARP at same moment |
| ARP sweep speed | <30 seconds for /24 | Timed from scan trigger to DB write |
| Standard scan speed | <60 seconds | End-to-end |
| Device persistence | All devices retained across container restart | Restart container; verify inventory unchanged |
| API availability | `GET /api/v1/system/health` returns 200 | Health check endpoint |

---

## Scope

### In Scope
- Docker Compose stack: `netsentry` container (host networking, CAP_NET_RAW), `ntfy` container, optional `redis` container
- Python project skeleton: `uv` package management, `pyproject.toml`, ruff, mypy, pytest, pre-commit
- Alembic: initial migration creating all core tables (devices, ip_assignments, events, scan_runs, system_config, notifications, tags, device_tags, deletion_audit_log)
- Scanner Engine: ARP sweep (arp-scan + scapy), ICMP sweep (fping), TCP SYN probe (python-nmap), mDNS listener (scapy multicast), SSDP/UPnP listener, NetBIOS scan (nbtscan)
- Scan profiles: Quick (ARP + ICMP), Standard (+ common ports), Deep (+ OS fingerprint + full port scan)
- Scheduled scans via APScheduler (ARP every 5 min, ports every 15 min, deep daily)
- MAC OUI resolution from bundled Wireshark manuf file; background weekly refresh
- Hostname resolution: mDNS, NetBIOS, DNS PTR
- Device inventory repository (async CRUD on `devices`, `ip_assignments`, `events`, `scan_runs`)
- Online/offline state management (offline after 2 consecutive missed cycles)
- FastAPI skeleton with OpenAPI docs; initial endpoints: `GET /api/v1/devices`, `GET /api/v1/devices/{mac}`, `POST /api/v1/scan/trigger`, `GET /api/v1/scan/status`, `GET /api/v1/system/health`
- Development compose file with `MOCK_INTEGRATIONS=true` support and hot-reload
- `docker-compose.yml` and `docker-compose.dev.yml`
- Basic React frontend scaffold (Vite + TypeScript + shadcn/ui + Tailwind): device table showing MAC, IP, vendor, hostname, online status, last seen

### Out of Scope
- Deco / pfSense / AdGuard integrations (EP0002, EP0003)
- Push notifications beyond logging (EP0004)
- Device identification pipeline (EP0005)
- Device categorisation / ownership UI (EP0006)
- Availability monitoring (EP0007)
- Speed testing (EP0008)
- Full dashboard with all panels (EP0009)

### Affected Personas
- **Primary Operator:** Direct beneficiary — gains continuous network visibility for the first time
- **Household Members:** Indirect; not yet impacted at this phase

---

## Acceptance Criteria (Epic Level)

- [ ] `docker compose up -d` starts the full stack from a clean clone with only `.env` configured
- [ ] Container healthcheck (`GET /api/v1/system/health`) returns 200 within 60 seconds of startup
- [ ] ARP sweep discovers all devices present in the pfSense ARP table within one scan cycle
- [ ] /24 ARP sweep completes in under 30 seconds
- [ ] Standard scan (ARP + common ports) completes in under 60 seconds
- [ ] Device records persist across container restart (SQLite volume mount)
- [ ] Alembic migrations run automatically at startup and are idempotent
- [ ] `GET /api/v1/devices` returns all discovered devices with MAC, IP, vendor, hostname, online status
- [ ] On-demand scan triggered via `POST /api/v1/scan/trigger` starts within 2 seconds
- [ ] New device joining the network appears in inventory within one scan cycle
- [ ] Device marked offline after 2 consecutive missed scan cycles (configurable)
- [ ] OUI database bundled in image; background weekly refresh succeeds without restart
- [ ] React device table renders correctly and updates on page reload
- [ ] Container runs as UID 1000 non-root; only `CAP_NET_RAW` capability granted
- [ ] ruff, mypy, and pytest all pass in CI (pre-commit hooks configured)

---

## Dependencies

### Blocked By
| Dependency | Type | Status |
|------------|------|--------|
| Docker host with network access to LAN | Infrastructure | Operator responsibility |
| `network_mode: host` available on Docker host | Infrastructure | Operator responsibility |

### Blocking
| Item | Impact |
|------|--------|
| EP0002 (Deco Integration) | Requires device inventory and repository layer |
| EP0003 (pfSense Integration) | Requires device inventory and repository layer |
| EP0004 (Notifications) | Requires Event Engine from this epic |
| EP0005 (Identification) | Requires scanner signal data from this epic |
| All subsequent epics | Foundation dependency |

---

## Risks & Assumptions

### Assumptions
- Docker host supports `network_mode: host` (standard Linux hosts; not available on Docker Desktop for Mac/Windows — documented limitation)
- `arp-scan`, `nmap`, `fping`, `nbtscan` installable in Python 3.12 slim base image

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| macvlan required on some hosts instead of host networking | Medium | Medium | Document macvlan alternative in deployment guide; test both configs |
| nmap OS fingerprinting produces unreliable results for some device types | High | Low | OS fingerprint is one signal only; not required for core inventory |
| arp-scan or fping not available in chosen base image | Low | Medium | Include in Dockerfile RUN layer with explicit version pins |

---

## Technical Considerations

### Architecture Impact
- Establishes the entire Python project structure: `netsentry/scanner/`, `netsentry/db/`, `netsentry/api/`, `netsentry/core/` (config, logging, scheduler bootstrap)
- Repository pattern established here becomes the contract for all subsequent epics
- APScheduler `AsyncIOScheduler` lifecycle management (start/stop hooks in FastAPI lifespan) established here
- Alembic migration chain started — all future epics add migrations on top

### Integration Points
- None external in this epic — scanner operates entirely on-network via raw sockets and subprocess tools
- `netsentry/integrations/` directory scaffold created but empty (populated by EP0002–EP0004)

---

## Sizing

**Story Points:** 34
**Estimated Story Count:** 8

**Complexity Factors:**
- Docker host networking + CAP_NET_RAW setup is non-trivial to test in CI
- Multiple scanning tools (arp-scan, scapy, nmap, fping, nbtscan) each need wrapping and error handling
- Async SQLite + APScheduler + FastAPI lifespan management requires careful initialisation order
- mDNS/SSDP multicast listeners run as long-lived async tasks alongside APScheduler

---

## Story Breakdown

- [ ] US0001: Docker Compose stack skeleton (netsentry + ntfy containers, volumes, health check)
- [ ] US0002: Python project scaffold (uv, pyproject.toml, ruff, mypy, pytest, pre-commit, FastAPI skeleton, Alembic init)
- [ ] US0003: SQLite schema + Alembic initial migration (all core tables)
- [ ] US0004: Device repository layer (async CRUD: devices, ip_assignments, scan_runs, events)
- [ ] US0005: Scanner Engine — ARP sweep + ICMP sweep + NetBIOS (discovery foundation)
- [ ] US0006: Scanner Engine — TCP port scan + mDNS/SSDP listeners + OS fingerprinting
- [ ] US0007: APScheduler task harness + scan profiles (Quick / Standard / Deep) + OUI resolution
- [ ] US0008: FastAPI device endpoints + React device table scaffold

---

## Open Questions

- [ ] Should nmap be called via `python-nmap` wrapper or direct subprocess? `python-nmap` is simpler but adds a dependency. — Owner: Implementation decision
- [ ] Should the OUI manuf file be bundled in the Docker image or downloaded on first run? (TRD open question #5) — Owner: Implementation decision; recommended: bundle in image

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft from PRD v1.1 + TRD v1.0 |
