# EP0005: Real-Time Availability Monitoring

> **Status:** Draft
> **Phase:** 4 — Polish & Advanced Monitoring
> **Created:** 2026-03-21
> **PRD Reference:** [PRD](../prd.md) · [TRD](../trd.md)

## Summary

Delivers per-device real-time availability monitoring: an independent high-frequency probe loop (minimum 10-second interval) that operates entirely outside the main 5-minute scan cycle. Each opted-in device can be probed via ICMP ping, TCP port check, or HTTP health check. State change alerts (up → down, down → up) fire immediately via all configured notification channels. Uptime statistics (24h/7d/30d) and a full state-change history are stored and surfaced in the dashboard.

---

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| PRD NFR | Performance | Availability alert latency ≤15s from first probe failure to notification dispatch | Probe → event → notification pipeline must complete in <15s |
| PRD | Scalability | Maximum 50 concurrently monitored devices (configurable via `AVAILABILITY_MAX_MONITORED`) | Enforce cap at enable endpoint |
| PRD | Alerting | Availability alerts bypass quiet hours (urgent priority) | Notification Engine priority override for availability events |
| TRD | Architecture | Availability Monitor runs as independent APScheduler task; does not block main scan cycle | Separate scheduler job; async probe execution |
| TRD | Security | `CAP_NET_RAW` already granted to scanner container | ICMP raw socket available |

---

## Business Context

### Problem Statement
The main 5-minute scan cycle is too coarse for critical devices (home server, NAS, primary router). The operator needs to know within seconds if a key device goes offline — not within the next scan window.

**PRD Reference:** PRD §3 — Real-Time Availability Monitoring

### Value Proposition
The operator can mark their most critical devices (NAS, home server, pfSense box, key IoT hubs) for real-time monitoring and receive an urgent push notification within 15 seconds of a device going offline. Recovery notifications include the outage duration. The dashboard's Monitored Devices panel gives an at-a-glance operational status board.

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Alert latency | ≤15s from first failed probe to notification dispatch | Timed test: block ICMP to a monitored device |
| Recovery alert | Includes correct outage duration | Timed test: restore device after known outage window |
| Uptime accuracy | 24h uptime % within ±1% of actual | Compare calculated uptime vs manually recorded uptime |
| Concurrent device cap | System stable with 50 monitored devices at 30s interval | Load test with 50 mock probe targets |
| Probe method coverage | ICMP, TCP, and HTTP probes all functional | Integration test one device per method |

---

## Scope

### In Scope
- `availability_monitors` table (Alembic migration): per-device config (enabled, interval, probe_method, probe_port, probe_url_path, consecutive_failures_threshold, current_state)
- `availability_events` table (Alembic migration): state transitions (up/down, timestamp, duration_seconds on recovery)
- Availability Monitor module (`netsentry/monitor/`): async probe runner, per-device state machine
- Probe implementations: ICMP ping (raw socket, `CAP_NET_RAW`), TCP connect (asyncio), HTTP GET (httpx)
- APScheduler dynamic job management: add/remove per-device probe jobs when monitoring enabled/disabled
- State machine per device: unknown → up / down; consecutive failure counting; state change event generation
- Alert fires on up→down and down→up transitions via Event Engine → Notification Engine (urgent priority, bypasses quiet hours)
- Alert payload: device friendly name, IP, MAC, category, owner, time of transition, outage duration (on recovery)
- Uptime calculation: rolling 24h, 7d, 30d uptime percentage from `availability_events`
- Maximum 50 concurrent monitored devices (configurable); enforce at `POST /api/v1/availability/{mac}/enable`
- New API endpoints:
  - `GET /api/v1/availability` — list all monitored devices with current state
  - `GET /api/v1/availability/{mac}` — uptime stats + event history
  - `POST /api/v1/availability/{mac}/enable` — enable monitoring with config
  - `DELETE /api/v1/availability/{mac}` — disable monitoring
- Device detail page: availability toggle, current state badge, uptime stats (24h/7d/30d)
- Dashboard "Monitored Devices" panel: all monitored devices, current up/down state, 24h uptime %
- `availability_events` pruned after 90 days (configurable)

### Out of Scope
- Internet speed testing (EP0006)
- Network-wide availability reporting (this is per-device opt-in only)
- SLA reporting or export
- Availability data for non-opted-in devices (main scan cycle covers those)

### Affected Personas
- **Primary Operator:** Gains real-time awareness of critical device status
- **Household Members:** Indirectly benefit if shared devices (NAS, smart home hub) are monitored

---

## Acceptance Criteria (Epic Level)

- [ ] Monitoring can be enabled per device via `POST /api/v1/availability/{mac}/enable` with interval, probe_method, and optional probe_port/URL path
- [ ] Monitored devices are probed independently of the main 5-minute scan cycle
- [ ] ICMP probe works without root using raw socket (CAP_NET_RAW already granted)
- [ ] TCP probe successfully detects open/closed port state changes
- [ ] HTTP probe detects non-200 responses as failures
- [ ] Device transitions to "down" state after configured consecutive failures (default: 2)
- [ ] Alert dispatched within 15 seconds of the first failed probe that triggers a down transition
- [ ] Recovery alert includes correct outage duration (time from down transition to up transition)
- [ ] Availability alerts are urgent priority and bypass quiet hours
- [ ] `GET /api/v1/availability/{mac}` returns 24h, 7d, and 30d uptime percentage
- [ ] `GET /api/v1/availability` returns all monitored devices with current state
- [ ] Enabling monitoring on the 51st device (beyond cap) returns a 409 error with clear message
- [ ] Disabling monitoring removes the probe job and stops all probes for that device
- [ ] Dashboard Monitored Devices panel shows all monitored devices with current up/down state
- [ ] Device detail page shows availability toggle and uptime stats for monitored devices
- [ ] Availability event history pruned after 90 days (default)

---

## Dependencies

### Blocked By
| Dependency | Type | Status |
|------------|------|--------|
| EP0001 complete | Epic | Must be Done — device inventory, Event Engine, Notification Engine required |
| EP0002 complete | Epic | Must be Done — Notification Engine (ntfy, Telegram) required for alert dispatch |

### Blocking
| Item | Impact |
|------|--------|
| EP0007 (Full Dashboard) | Monitored Devices panel and availability tabs in device detail |

---

## Risks & Assumptions

### Assumptions
- `CAP_NET_RAW` (already granted for ARP scanning) is sufficient for raw ICMP sockets on the Docker host
- 50 devices × 30s interval = ~1.7 probes/second; well within asyncio capacity

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Raw ICMP not available in some Docker environments (e.g., rootless Docker) | Low | Medium | Fall back to TCP probe method as default if ICMP socket creation fails; log warning |
| False positive "down" alerts for devices that go to sleep (phone screen off) | High | Medium | Configurable consecutive_failures_threshold (default 2); grace period; document expected behaviour for sleep-mode devices |
| Probe storm if many devices configured with minimum 10s interval | Low | Low | Cap at 50 devices; minimum interval 10s; probes are async and non-blocking |

---

## Technical Considerations

### Architecture Impact
- `netsentry/monitor/` package: `manager.py` (job lifecycle, cap enforcement), `prober.py` (ICMP/TCP/HTTP probe implementations), `state_machine.py` (per-device up/down/unknown state)
- APScheduler dynamic job creation/deletion when monitor enable/disable called
- Event Engine extended: `availability.down` and `availability.up` event types with urgent severity
- Alembic migration 0005: `availability_monitors`, `availability_events`

### Integration Points
- ICMP: raw socket on loopback/LAN interface (in-process, no external service)
- TCP: `asyncio.open_connection()` (in-process)
- HTTP: `httpx.AsyncClient` GET to device IP (in-process)
- All alerts routed through existing Notification Engine (EP0002)

---

## Sizing

**Story Points:** 21
**Estimated Story Count:** 5

**Complexity Factors:**
- Raw ICMP socket implementation in async Python requires careful error handling
- Per-device dynamic APScheduler job lifecycle (add/remove at runtime) is non-trivial
- State machine must handle edge cases: device never seen (unknown), immediate recovery, probe timeout vs connection refused

---

## Story Breakdown

- [ ] US0029: `availability_monitors` + `availability_events` tables + repository layer
- [ ] US0030: Probe implementations (ICMP raw socket, TCP asyncio, HTTP httpx) + per-device state machine
- [ ] US0031: Availability Monitor manager (dynamic APScheduler jobs, cap enforcement, probe orchestration)
- [ ] US0032: Availability Event Engine integration + Notification Engine dispatch (urgent, bypass quiet hours)
- [ ] US0033: Availability API endpoints + Dashboard Monitored Devices panel + Device detail availability UI

---

## Open Questions

- [ ] Should the consecutive_failures_threshold be per-device configurable or global? Recommended: per-device (stored in availability_monitors), with global default from config. — Owner: Implementation decision
- [ ] Should uptime % be calculated on-the-fly from availability_events at query time, or pre-aggregated periodically? Recommended: on-the-fly for accuracy; cache result in availability_monitors for dashboard performance. — Owner: Implementation decision

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft from PRD v1.1 + TRD v1.0 |
