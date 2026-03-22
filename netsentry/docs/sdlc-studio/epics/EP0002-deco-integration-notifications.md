# EP0002: Deco Mesh Integration & Push Notifications

> **Status:** Draft
> **Phase:** 2 — Deco Mesh + Notifications
> **Created:** 2026-03-21
> **PRD Reference:** [PRD](../prd.md) · [TRD](../trd.md)

## Summary

Integrates the TP-Link Deco mesh system to surface per-device wireless intelligence (AP node assignment, Wi-Fi band, real-time speed) and the mesh topology. Simultaneously builds the complete Notification Engine — ntfy (self-hosted push) and Telegram Bot API — with the Event Engine that detects device state changes and dispatches alerts. After this epic the operator receives real-time phone notifications for new devices and can see which Deco node each device connects through.

---

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| PRD | Security | Deco owner credentials stored as Docker secrets only | No credentials in DB or logs |
| PRD | Compatibility | Deco in Access Point mode; single owner session at a time | Auto re-auth on 403; document manager account separation |
| TRD ADR-006 | Telegram | Plain Markdown + deep-link URL only; no inline keyboard | `sendMessage` API only; no bot polling loop |
| PRD NFR | Performance | Deco data freshness ≤30s; ntfy ≤5s Android / ≤15s iOS | Polling interval 30s; ntfy upstream relay for iOS |
| TRD | Integration | All integration failures non-fatal; degrade gracefully | Event Engine and API must handle missing Deco data |

---

## Business Context

### Problem Statement
The operator's TP-Link Deco mesh shows which devices are connected in the app, but there is no way to correlate this with the rest of the network, automate on it, or receive push alerts when something unexpected joins. They have no real-time phone alerts for network events.

**PRD Reference:** PRD §3 — TP-Link Deco Mesh Integration; Push Notifications (ntfy + Telegram)

### Value Proposition
The operator receives an instant phone notification when an unknown device joins the network, with a link to view it in the dashboard. They can also see which Deco node each device is connected to, what Wi-Fi band it uses, and real-time per-device wireless throughput — intelligence not available from any other source.

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Deco client parity | 100% of Deco app clients in NetSentry | Compare Deco app client count vs NetSentry at same moment |
| AP node assignment accuracy | 100% of wireless devices show correct Deco node | Manual spot-check vs Deco app |
| ntfy alert latency | ≤5s Android, ≤15s iOS | Time from event to phone notification receipt |
| Telegram alert latency | ≤5s to Telegram API | Event timestamp vs notification sent_at |
| Notification reliability | 0 missed alerts for new-device events | Manual test: connect 5 new devices, verify 5 alerts |

---

## Scope

### In Scope
- Deco local API client: AES/RSA encrypted JSON protocol, session management, auto-re-auth on 403
- Deco poller (APScheduler, 30s default): client list (MAC, IP, hostname, type, band, speed, AP node), mesh topology (node list, roles, health), Deco node table in DB
- `mesh_assignments` and `deco_nodes` tables (Alembic migration)
- Enrichment of device records with Deco data (AP node, band, connection type, per-device speed)
- Roaming event detection (device moves between Deco nodes)
- Deco satellite node offline alert
- Event Engine: state change detection for new device, device online/offline, Deco node offline
- Notification Engine: ntfy channel (HTTP PUT/POST, priority levels, deep-link URLs, quiet hours, rate limiting)
- Telegram channel: `sendMessage` API, Markdown formatting, deep-link URL, Bot token from Docker secret
- `notifications` table populated by Notification Engine
- Per-alert-type channel routing config (stored in `system_config`)
- Grace period for transient new-device alerts
- Test notification endpoint: `POST /api/v1/notifications/test/{channel}`
- New API endpoints: `GET /api/v1/deco/topology`, `GET /api/v1/notifications/config`
- Dashboard Deco panel: mesh topology map (nodes + connected clients)
- Settings UI: ntfy config, Telegram config, quiet hours, per-alert routing

### Out of Scope
- pfSense / AdGuard integrations (EP0003)
- Device identification AI (EP0005)
- Availability monitoring notifications (EP0007)
- Speed test notifications (EP0008)
- Apprise multi-channel (deferred; ntfy + Telegram cover primary use cases)

### Affected Personas
- **Primary Operator:** Receives instant phone alerts; gains Deco mesh visibility in dashboard
- **Household Members:** Indirectly impacted if their devices trigger alerts

---

## Acceptance Criteria (Epic Level)

- [ ] Deco poller connects, authenticates, and polls client list every 30 seconds
- [ ] Every client visible in the Deco app appears in NetSentry with correct AP node and Wi-Fi band
- [ ] Deco data cross-references pfSense DHCP (when available) to resolve IPs shown as "UNKNOWN" by Deco in AP mode
- [ ] Roaming event (device moves between Deco nodes) detected and stored as an event
- [ ] Alert fired when a Deco satellite node goes offline
- [ ] System continues operating normally if Deco is unreachable (scanner-only mode)
- [ ] ntfy alert delivered to Android phone within 5 seconds of a new device joining
- [ ] Telegram `sendMessage` fires within 5 seconds; message contains device name, IP, and deep-link URL
- [ ] Both ntfy and Telegram active simultaneously; alerts reach both channels
- [ ] Quiet hours suppress non-critical notifications; urgent alerts (unknown device) bypass quiet hours
- [ ] Rate limiting prevents >1 alert per device per alert type within the aggregation window
- [ ] `POST /api/v1/notifications/test/ntfy` and `/test/telegram` deliver test messages
- [ ] Notification records written to `notifications` table with status (sent/failed/suppressed)
- [ ] Deco mesh topology visible in dashboard panel

---

## Dependencies

### Blocked By
| Dependency | Type | Status |
|------------|------|--------|
| EP0001 complete | Epic | Must be Done |
| Deco owner credentials available | Operator config | Operator responsibility |
| Telegram Bot token + Chat ID available | Operator config | Optional; Telegram disabled if not configured |

### Blocking
| Item | Impact |
|------|--------|
| EP0005 (Identification) | Deco device type field is an identification signal |
| EP0009 (Dashboard) | Deco topology panel depends on this epic |

---

## Risks & Assumptions

### Assumptions
- Deco firmware version is compatible with the ha-tplink-deco encrypted JSON API
- Operator has Deco owner credentials; a separate manager account exists or will be created for the Deco mobile app

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Deco firmware update breaks encrypted JSON protocol | Medium | High | Pin to known working firmware; isolate crypto in `deco/crypto.py`; monitor ha-tplink-deco community for breaking changes |
| Deco AP mode returns "UNKNOWN" for all IPs (no pfSense integration yet in this phase) | High | Low | Store "UNKNOWN" as-is; EP0003 resolves via pfSense DHCP cross-reference |
| Telegram Bot token leakage via logs | Low | Medium | Configure httpx log level to exclude Authorization/Cookie; secrets in Docker secrets only |
| ntfy iOS delivery delayed without upstream relay | Medium | Medium | Document `NTFY_UPSTREAM_BASE_URL` config; default config example includes ntfy.sh relay |

---

## Technical Considerations

### Architecture Impact
- `netsentry/integrations/deco/` package: `client.py` (HTTP + session), `crypto.py` (AES/RSA), `poller.py` (APScheduler task), `models.py` (dataclasses)
- `netsentry/events/` package introduced: `engine.py` (state change detection), `dispatcher.py` (routes to Notification Engine)
- `netsentry/notifications/` package: `ntfy.py`, `telegram.py`, `engine.py` (channel routing, rate limiting, quiet hours)
- Alembic migration 0002: `mesh_assignments`, `deco_nodes` tables

### Integration Points
- Deco main node: HTTP/HTTPS to Deco IP, encrypted JSON (AES-CBC, RSA key exchange)
- ntfy: HTTP PUT/POST to local ntfy container (`http://ntfy:80/netsentry`)
- Telegram: HTTPS POST to `https://api.telegram.org/bot{token}/sendMessage`

---

## Sizing

**Story Points:** 29
**Estimated Story Count:** 7

**Complexity Factors:**
- Deco encrypted JSON protocol implementation is the highest-complexity item (AES/RSA, session lifecycle)
- Notification Engine must handle concurrent channel dispatch, rate limiting, quiet hours, and failure isolation in one coherent module
- Two notification channels (ntfy + Telegram) with different auth and payload formats

---

## Story Breakdown

- [ ] US0009: Deco API client (encrypted JSON protocol, auth, session management, auto-re-auth)
- [ ] US0010: Deco poller + DB persistence (client list, AP node, band, speed; mesh topology; deco_nodes table)
- [ ] US0011: Deco enrichment + roaming detection (merge Deco data into device records, roaming events)
- [ ] US0012: Event Engine (state change detection: new device, offline, Deco node down; event DB writes)
- [ ] US0013: Notification Engine — ntfy channel (HTTP dispatch, priority, deep-link, quiet hours, rate limiting)
- [ ] US0014: Notification Engine — Telegram channel (sendMessage, Markdown, deep-link, Bot token secret)
- [ ] US0015: Notification config API + Settings UI + Deco topology dashboard panel

---

## Open Questions

- [ ] Should the Deco poller use `asyncio` sleep loops or APScheduler interval jobs? APScheduler preferred for consistency with other pollers. — Owner: Implementation decision
- [ ] How should the Notification Engine handle partial failures (ntfy succeeds, Telegram fails)? Both attempts should be made; each logged independently. — Owner: Implementation decision

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft from PRD v1.1 + TRD v1.0 |
