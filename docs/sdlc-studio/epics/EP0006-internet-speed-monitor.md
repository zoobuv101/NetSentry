# EP0006: Internet Speed Monitor

> **Status:** Draft
> **Phase:** 4 — Polish & Advanced Monitoring
> **Created:** 2026-03-21
> **PRD Reference:** [PRD](../prd.md) · [TRD](../trd.md)

## Summary

Delivers scheduled internet speed testing (download, upload, latency, jitter, packet loss) using LibreSpeed by default (self-hosted, privacy-preserving) with Ookla as an opt-in alternative. Results are stored with full history, surfaced in the dashboard with trend sparklines and a full history chart, and generate alerts when speeds drop below configurable thresholds. Speed events are correlated with the network event timeline.

---

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| TRD ADR-004 | Speed test | LibreSpeed default; Ookla opt-in via `SPEEDTEST_BACKEND=ookla` | LibreSpeed container in Compose when `ENABLE_LIBRESPEED=true` |
| PRD NFR | Performance | Speed test runs in subprocess; does not block API or availability monitor | `subprocess` + asyncio `run_in_executor`; never on the event loop |
| PRD | Data | `SpeedTestResult` records retained 365 days (configurable) | Pruning job in APScheduler |
| PRD | Privacy | LibreSpeed self-hosted preferred; no Ookla data sent to third parties by default | Default config uses local LibreSpeed container |

---

## Business Context

### Problem Statement
The operator has no visibility into whether their ISP is consistently delivering contracted speeds. Speed drops happen silently — the operator only notices when streaming buffers or a file download feels slow. There is no historical record to present to the ISP.

**PRD Reference:** PRD §3 — Internet Speed Monitor

### Value Proposition
NetSentry automatically tests internet speed every 6 hours (configurable), stores all results, and alerts the operator if speeds fall below a threshold for two consecutive tests. The dashboard shows a trend sparkline alongside device data, and the full history page lets the operator identify patterns (e.g., consistent evening slowdowns) and build a case for the ISP.

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test reliability | <5% failed tests on a stable connection | Count `tested_at` records vs expected over 7 days |
| Speed correlation accuracy | Download result within ±10% of manual Speedtest.net test | Run both simultaneously; compare results |
| Alert trigger | Alert fires when download <50% of 10-test median for 2 consecutive tests | Simulated by manually reducing threshold |
| Dashboard freshness | Latest result displayed within 10s of test completion | Observe dashboard after triggering manual test |

---

## Scope

### In Scope
- `speed_test_results` table (Alembic migration): download_mbps, upload_mbps, ping_ms, jitter_ms, packet_loss_pct, server_name, server_location, backend, tested_at
- Speed Monitor module (`netsentry/speedtest/`): subprocess runner (librespeed-cli / speedtest-cli), result parser, result writer
- LibreSpeed: `linuxserver/librespeed` Docker service added to `docker-compose.yml` when `ENABLE_LIBRESPEED=true`; `librespeed-cli` installed in netsentry container
- Ookla: `speedtest-cli` installed in netsentry container (available when `SPEEDTEST_BACKEND=ookla`)
- APScheduler scheduled job (default: every 6 hours, configurable via `SPEEDTEST_INTERVAL`)
- On-demand trigger: `POST /api/v1/speedtest/trigger`
- Threshold alerting: download or upload below configurable threshold for 2 consecutive tests; latency exceeds threshold; routed via Event Engine → Notification Engine
- Baseline calculation: median of last 10 tests; threshold comparison uses this rolling baseline when absolute thresholds not set
- Speed test skipped (no alert) when test server is unreachable; failure logged
- 365-day retention; APScheduler pruning job
- New API endpoints:
  - `GET /api/v1/speedtest/results` — history with `?limit=` and `?range=` params
  - `GET /api/v1/speedtest/latest` — most recent result
  - `POST /api/v1/speedtest/trigger` — on-demand
- Dashboard Speed panel: latest download/upload/latency, trend sparklines (24h and 7d)
- Full speed history page: time-series chart (Recharts), selectable range (24h/7d/30d/all), download + upload + latency overlaid; avg/min/max/p95 stats table
- Speed events annotated on the main network events timeline
- Settings UI: speed test backend selector, interval config, download/upload/latency threshold inputs

### Out of Scope
- Per-device speed (Deco provides wireless per-device speed; no LAN per-device speed test)
- ISP reporting automation
- Multi-server testing or server selection UI

### Affected Personas
- **Primary Operator:** Gains ISP performance visibility and alerting
- **Household Members:** Indirectly benefit from speed alerting

---

## Acceptance Criteria (Epic Level)

- [ ] Speed test runs automatically on the configured schedule (default: every 6 hours)
- [ ] LibreSpeed test completes when `ENABLE_LIBRESPEED=true` and LibreSpeed container is running
- [ ] Ookla test completes when `SPEEDTEST_BACKEND=ookla` is set
- [ ] Result stored in `speed_test_results` with download, upload, ping, jitter, packet_loss, server_name, backend, tested_at
- [ ] On-demand test triggered via `POST /api/v1/speedtest/trigger` starts within 5 seconds
- [ ] Speed test subprocess does not block API responses (runs in executor)
- [ ] Alert fires when download OR upload falls below configured threshold for 2 consecutive tests
- [ ] Latency threshold alert fires when ping exceeds configured threshold
- [ ] No alert when test server is unreachable; failure logged only
- [ ] `GET /api/v1/speedtest/latest` returns the most recent result within 200ms
- [ ] `GET /api/v1/speedtest/results?range=7d` returns correct date-filtered results
- [ ] Dashboard Speed panel shows latest values and 24h/7d sparklines
- [ ] Speed history page renders time-series chart for selectable range
- [ ] avg/min/max/p95 statistics correct for selected range
- [ ] Speed drop events appear on the network events timeline
- [ ] Records older than retention window (default 365 days) are pruned by scheduled job

---

## Dependencies

### Blocked By
| Dependency | Type | Status |
|------------|------|--------|
| EP0001 complete | Epic | Must be Done — APScheduler, Event Engine, Notification Engine required |
| EP0002 complete | Epic | Must be Done — Notification Engine for speed alerts |
| Internet connectivity on Docker host | Infrastructure | Operator responsibility |

### Blocking
| Item | Impact |
|------|--------|
| EP0007 (Full Dashboard) | Speed panel and history page |

---

## Risks & Assumptions

### Assumptions
- `librespeed-cli` and `speedtest-cli` are installable in the Python 3.12 slim base image
- LibreSpeed self-hosted container on LAN gives accurate WAN throughput measurement (tests the operator's ISP connection, not the LAN)
- Docker host has outbound internet access for speed testing

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| speedtest-cli (Ookla) requires account token for automated use | Medium | Medium | Document Ookla terms; default to LibreSpeed; Ookla is opt-in |
| Speed test consumes significant bandwidth during test | Medium | Low | Document test bandwidth usage (~100MB per test); allow operator to schedule during off-peak hours |
| LibreSpeed self-hosted container measures LAN speed to container, not WAN speed | Low | High | LibreSpeed must be accessed via the Docker host's external IP or configured with WAN-reachable URL; document correctly |

---

## Technical Considerations

### Architecture Impact
- `netsentry/speedtest/` package: `runner.py` (subprocess management, asyncio executor), `parsers/librespeed.py`, `parsers/ookla.py`, `scheduler.py`
- `linuxserver/librespeed` added to `docker-compose.yml` as optional service
- Alembic migration 0006: `speed_test_results`
- Event Engine extended: `speedtest.threshold_breach` event type
- APScheduler maintenance job: prune `speed_test_results` older than retention window

### Integration Points
- LibreSpeed: `librespeed-cli` subprocess → local Docker container (`http://librespeed:8888`)
- Ookla: `speedtest-cli` subprocess → Speedtest.net (internet)
- All alerts via existing Notification Engine

---

## Sizing

**Story Points:** 18
**Estimated Story Count:** 4

**Complexity Factors:**
- Two subprocess-based backends (librespeed-cli, speedtest-cli) with different JSON output formats
- Recharts time-series chart with selectable range and multiple overlaid series requires frontend effort
- Baseline calculation and threshold logic needs careful edge case handling (< 10 historical tests)

---

## Story Breakdown

- [ ] US0034: `speed_test_results` table + Speed Monitor module (subprocess runner, LibreSpeed + Ookla parsers, APScheduler job)
- [ ] US0035: Threshold alerting (rolling baseline, consecutive test logic, Event Engine integration)
- [ ] US0036: Speed test API endpoints + Dashboard Speed panel (latest values + sparklines)
- [ ] US0037: Full speed history page (Recharts time-series, range selector, stats table) + event timeline annotation + LibreSpeed Docker Compose service

---

## Open Questions

- [ ] Should the LibreSpeed container be on the bridge network (only accessible from other containers) or exposed on a host port so the operator can also manually test from a browser? Recommended: expose on host port (e.g., 8888) so both NetSentry and the operator can use it. — Owner: Implementation decision
- [ ] Should the rolling baseline (median of last 10 tests) be used when no absolute threshold is configured, or should absolute thresholds always be required? Recommended: absolute thresholds optional; if not set, no threshold alerting (explicit operator choice). — Owner: Implementation decision

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft from PRD v1.1 + TRD v1.0 |
