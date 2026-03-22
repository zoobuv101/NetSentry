# US0009: Deco API Client (Encrypted JSON Protocol, Auth, Session Management)

> **Status:** Ready
> **Epic:** [EP0002](../epics/EP0002-deco-integration-notifications.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** developer
**I want** a reliable Deco API client that handles the encrypted JSON protocol, session lifecycle, and auto-re-authentication
**So that** all Deco data polling in subsequent stories can use a simple, tested interface without worrying about protocol details

## Context

### Background
The TP-Link Deco local API uses an AES/RSA encrypted JSON protocol. This story implements the low-level client: RSA public key retrieval from the Deco admin, AES session key generation and encryption, `LoginRequest`/`LoginResponse` parsing, session cookie maintenance, and automatic re-authentication on 403 responses. All crypto logic is isolated in `deco/crypto.py`.

---

## Acceptance Criteria

### AC1: Client authenticates successfully
- **Given** valid Deco owner credentials in config and a running Deco unit (or mock server)
- **When** `DecoClient.authenticate()` is awaited
- **Then** a session cookie is stored in the httpx `CookieJar` and `authenticated=True` is returned

### AC2: Encrypted request/response round-trip works
- **Given** an authenticated client session
- **When** `DecoClient.request(method="POST", endpoint="/cgi-bin/luci/;stok=/ds", payload={"operation": "read"})` is awaited
- **Then** the encrypted JSON payload is sent; the encrypted response is decrypted and returned as a Python dict

### AC3: Auto re-auth on 403
- **Given** an authenticated client whose session has been invalidated (Deco app login)
- **When** any `DecoClient.request()` call receives HTTP 403
- **Then** `authenticate()` is called automatically; the original request is retried once; the response is returned normally

### AC4: Max one re-auth retry
- **Given** re-authentication also fails (wrong credentials)
- **When** a 403 is received and re-auth is attempted
- **Then** `DecoAuthError` is raised after one re-auth attempt; the error is logged; no infinite loop

### AC5: Credentials loaded from Docker secret files
- **Given** `DECO_USERNAME` and `DECO_PASSWORD` configured as Docker secrets at `/run/secrets/`
- **When** `DecoClient` is instantiated
- **Then** credentials are read from secret files (not env vars) when files exist; env var fallback used otherwise

### AC6: Client request times out gracefully
- **Given** the Deco main node is unreachable (network timeout)
- **When** `DecoClient.request()` is awaited with default 10s timeout
- **Then** `DecoConnectionError` is raised after 10 seconds; no hang

---

## Scope

### In Scope
- `netsentry/integrations/deco/crypto.py` — RSA key exchange, AES-CBC encrypt/decrypt
- `netsentry/integrations/deco/client.py` — `DecoClient` with `authenticate()`, `request()`, session management
- `netsentry/integrations/deco/exceptions.py` — `DecoAuthError`, `DecoConnectionError`, `DecoProtocolError`
- Mock Deco server for unit tests (httpx `MockTransport` or `pytest-httpx`)

### Out of Scope
- Data model parsing (US0010)
- APScheduler polling (US0010)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Deco at incorrect IP | `DecoConnectionError` within timeout |
| Wrong password | `DecoAuthError("Authentication failed: invalid credentials")` |
| Encrypted response payload malformed | `DecoProtocolError("Failed to decrypt response")` |
| Deco firmware changes encryption scheme | `DecoProtocolError` caught by poller; integration marked unhealthy |
| Concurrent requests during re-auth | Re-auth mutex prevents duplicate auth requests |

---

## Test Scenarios (TDD)

- [ ] `test_authenticate_stores_session_cookie`
- [ ] `test_request_encrypts_payload`
- [ ] `test_request_decrypts_response`
- [ ] `test_auto_reauth_on_403`
- [ ] `test_reauth_raises_after_one_retry`
- [ ] `test_timeout_raises_connection_error`
- [ ] `test_credentials_loaded_from_secret_file`
- [ ] `test_credentials_fallback_to_env_var`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0002 | Project | httpx, project scaffold | Ready |

## Estimation
**Story Points:** 5
**Complexity:** High — cryptographic protocol; mock server required

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0010: Deco Poller & DB Persistence

> **Status:** Ready
> **Epic:** [EP0002](../epics/EP0002-deco-integration-notifications.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** NetSentry to poll the Deco mesh every 30 seconds and store per-device AP node, Wi-Fi band, and speed data
**So that** I can see which Deco node each device connects through and track real-time wireless throughput

## Context

### Background
Implements the Deco poller APScheduler job, the `deco_nodes` and `mesh_assignments` Alembic migration (0002), and the repository classes for these tables. The poller calls `DecoClient` to retrieve the client list and mesh topology, maps Deco MACs to device inventory MACs (cross-reference via pfSense DHCP when IP is "UNKNOWN"), and writes enrichment data to the DB.

---

## Acceptance Criteria

### AC1: Deco client list polled every 30 seconds
- **Given** a configured and authenticated Deco client
- **When** the APScheduler Deco poller job runs
- **Then** `DecoClient.request()` is called with the `client_list` endpoint; result is stored in `mesh_assignments`

### AC2: Client list data stored correctly
- **Given** Deco returns a client at MAC `aa:bb:cc:11:22:33` connected to Deco node `dd:ee:ff:44:55:66`, band `5GHz`, download `25.5 Mbps`
- **When** the poller processes this response
- **Then** a `mesh_assignments` row exists with `mac_address="aa:bb:cc:11:22:33"`, `deco_node_mac="dd:ee:ff:44:55:66"`, `band="5GHz"`, `download_speed_bps=26738688`

### AC3: Deco node list stored in `deco_nodes` table
- **Given** Deco reports 2 nodes: one main, one satellite
- **When** the poller processes the device list response
- **Then** 2 rows exist in `deco_nodes` with correct `role` (main/satellite), `is_online=1`

### AC4: Device record enriched with Deco data
- **Given** a device `aa:bb:cc:11:22:33` exists in the `devices` table
- **When** the Deco poller runs and sees this device connected wirelessly
- **Then** `devices.connection_type="wireless"` is updated

### AC5: Deco "UNKNOWN" IP cross-referenced
- **Given** Deco reports a device with IP "UNKNOWN" (AP mode) and MAC `aa:bb:cc:11:22:33`
- **And** the `ip_assignments` table has a row for this MAC with `ip="192.168.1.55"`
- **When** the poller processes this device
- **Then** `mesh_assignments.last_known_ip="192.168.1.55"` is set from the cross-reference

### AC6: Graceful degradation when Deco unreachable
- **Given** `DecoClient.request()` raises `DecoConnectionError`
- **When** the poller job runs
- **Then** the error is logged as WARNING; the job completes without exception; existing `mesh_assignments` data is not deleted

---

## Scope

### In Scope
- Alembic migration `0002_deco.py` — `mesh_assignments`, `deco_nodes` tables
- `netsentry/db/repositories/deco.py` — `MeshAssignmentRepository`, `DecoNodeRepository`
- `netsentry/integrations/deco/poller.py` — `DecoPoller` APScheduler job
- `netsentry/integrations/deco/models.py` — `DecoClient`, `DecoNode` dataclasses
- Poller registration in scheduler startup

### Out of Scope
- Roaming event detection (US0011)
- Dashboard Deco panel (US0015)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Device in Deco client list but not in `devices` inventory | Device added to inventory with `source="deco"` |
| Deco node goes offline between polls | `deco_nodes.is_online=0`; `deco.node_offline` event created |
| Speed values missing from Deco response | Stored as NULL in mesh_assignments |
| Duplicate MAC in Deco client list | Last occurrence wins; WARNING logged |

---

## Test Scenarios (TDD)

- [ ] `test_poller_writes_mesh_assignment`
- [ ] `test_poller_writes_deco_nodes`
- [ ] `test_poller_enriches_device_connection_type`
- [ ] `test_unknown_ip_cross_reference`
- [ ] `test_graceful_degradation_on_connection_error`
- [ ] `test_new_device_from_deco_added_to_inventory`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0009 | Integration | DecoClient | Ready |
| US0004 | Data | Device repository | Ready |

## Estimation
**Story Points:** 5
**Complexity:** Medium

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0011: Deco Enrichment & Roaming Detection

> **Status:** Ready
> **Epic:** [EP0002](../epics/EP0002-deco-integration-notifications.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** to know when a device roams between Deco nodes and see which AP each device is connected to
**So that** I can identify Wi-Fi coverage issues and understand device movement through my home

## Context

### Background
Extends the Deco poller with roaming detection: compare the current Deco node assignment for each device against its previous assignment. If different, emit a `deco.device_roamed` event with from/to node info. Also implements the Deco satellite node offline alert.

---

## Acceptance Criteria

### AC1: Roaming event created when device moves between nodes
- **Given** device `aa:bb:cc:11:22:33` was connected to node `node-A` in the previous poll
- **When** the current poll shows it connected to `node-B`
- **Then** a `deco.device_roamed` Event is created with `details: {from_node: "node-A", to_node: "node-B"}` and the `mesh_assignments` row is updated

### AC2: No roaming event when device stays on same node
- **Given** device connected to `node-A` in both previous and current poll
- **When** the poller runs
- **Then** no `deco.device_roamed` Event is created

### AC3: Deco satellite node offline alert
- **Given** a satellite Deco node was `is_online=1` in the previous poll
- **When** the current poll's device_list shows it missing or offline
- **Then** `deco_nodes.is_online=0` and a `deco.node_offline` Event with `severity="urgent"` is created

### AC4: Satellite node recovery event
- **Given** a satellite node was `is_online=0`
- **When** it reappears in the device list
- **Then** `deco_nodes.is_online=1` and a `deco.node_online` Event is created

---

## Scope

### In Scope
- Roaming detection in `DecoPoller` (compare previous vs current node per device MAC)
- `deco.device_roamed`, `deco.node_offline`, `deco.node_online` event types in Event Engine
- Previous node state cached in-memory (last-seen node per device MAC)

### Out of Scope
- Notification dispatch (US0013/US0014)
- Dashboard topology panel (US0015)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Device first seen — no previous assignment | No roaming event; assignment stored as new |
| All Deco nodes offline simultaneously | All marked offline; `deco.node_offline` events for each |
| Main Deco node offline (not just satellite) | Same handling; marked offline; event created |

---

## Test Scenarios (TDD)

- [ ] `test_roaming_event_on_node_change`
- [ ] `test_no_event_same_node`
- [ ] `test_satellite_offline_event`
- [ ] `test_satellite_recovery_event`
- [ ] `test_first_seen_device_no_roaming_event`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0010 | Integration | Deco poller, mesh_assignments table | Ready |

## Estimation
**Story Points:** 3
**Complexity:** Low

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0012: Event Engine — State Change Detection & DB Writes

> **Status:** Ready
> **Epic:** [EP0002](../epics/EP0002-deco-integration-notifications.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** developer
**I want** a centralised Event Engine that detects state changes and writes typed events to the database
**So that** all alert logic flows through a single, testable, consistent path regardless of which component detected the change

## Context

### Background
Formalises the Event Engine started in US0007. Adds all EP0002 event types, implements alert rule evaluation (severity mapping, quiet hours check, rate limiting check), and wires the notification dispatch stub (actual dispatch implemented in US0013/US0014). After this story, any component can call `EventEngine.emit(event_type, mac, details)` and the Event Engine handles persistence and dispatch routing.

---

## Acceptance Criteria

### AC1: `EventEngine.emit()` writes event to DB
- **Given** a running Event Engine
- **When** `EventEngine.emit(event_type="device.new", mac_address="aa:bb:cc:dd:ee:ff", severity="urgent", details={"ip": "192.168.1.10"})` is awaited
- **Then** a row exists in the `events` table with correct fields; `notification_sent=0`

### AC2: Rate limiting suppresses duplicate alerts
- **Given** a `device.new` event for MAC `aa:bb:cc:dd:ee:ff` was emitted 30 seconds ago
- **When** another `device.new` event for the same MAC is emitted within the aggregation window (default: 300s)
- **Then** the second event is written to DB but marked suppressed; `EventEngine.should_dispatch()` returns `False`

### AC3: Quiet hours suppresses non-urgent events
- **Given** quiet hours are `22:00–07:00` and current time is `23:30`
- **When** `EventEngine.emit(event_type="scan.complete", severity="info")` is called
- **Then** `should_dispatch()` returns `False`; event still written to DB

### AC4: Urgent events bypass quiet hours
- **Given** quiet hours are active
- **When** `EventEngine.emit(event_type="device.new", severity="urgent")` is called
- **Then** `should_dispatch()` returns `True` regardless of quiet hours

### AC5: All EP0002 event types registered
- **Given** the Event Engine is initialised
- **When** each event type (`device.new`, `device.offline`, `device.online`, `deco.device_roamed`, `deco.node_offline`, `deco.node_online`) is emitted
- **Then** each writes successfully to DB with correct severity mapping

---

## Scope

### In Scope
- `netsentry/events/engine.py` — `EventEngine` with `emit()`, `should_dispatch()`, rate limiter, quiet hours check
- `netsentry/events/types.py` — event type registry with severity mappings
- Rate limiter: in-memory `{(mac, event_type): last_emitted_at}` dict; configurable window per event type

### Out of Scope
- Notification dispatch (US0013/US0014)
- Availability events (EP0005)
- Speed test events (EP0006)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| `emit()` called with unknown event_type | `ValueError("Unknown event type: ...")` |
| DB write fails during emit | Error logged; no exception propagated to caller (fire-and-forget) |
| Rate limiter dict grows large | LRU eviction after 1000 entries |
| Quiet hours span midnight (22:00–07:00) | Correctly handles midnight crossing |

---

## Test Scenarios (TDD)

- [ ] `test_emit_writes_event_to_db`
- [ ] `test_rate_limiting_suppresses_duplicate`
- [ ] `test_quiet_hours_suppresses_info_event`
- [ ] `test_urgent_bypasses_quiet_hours`
- [ ] `test_all_ep0002_event_types_valid`
- [ ] `test_unknown_event_type_raises`
- [ ] `test_rate_limiter_resets_after_window`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0004 | Data | EventRepository | Ready |
| US0007 | Events | Event Engine stub | Ready |

## Estimation
**Story Points:** 4
**Complexity:** Medium

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0013: Notification Engine — ntfy Channel

> **Status:** Ready
> **Epic:** [EP0002](../epics/EP0002-deco-integration-notifications.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** to receive push notifications on my phone via ntfy when network events occur
**So that** I am alerted to new or suspicious devices instantly without checking the dashboard

## Context

### Background
Implements the ntfy notification channel: HTTP PUT to the local ntfy container with correct topic, priority header (`x-priority`), title, message, and click URL (deep-link to device detail). Wires into the Event Engine so that `should_dispatch()` returning True triggers dispatch. Writes `notifications` table rows with sent/failed status.

---

## Acceptance Criteria

### AC1: ntfy notification sent for urgent event
- **Given** ntfy is configured and a `device.new` event (urgent) is emitted
- **When** `EventEngine.emit()` triggers dispatch
- **Then** `PUT http://ntfy:80/netsentry` is called with headers `x-priority: urgent`, `x-title: New Device Detected`, `x-click: http://<host>/devices/aa:bb:cc:dd:ee:ff`; body is the device name and IP

### AC2: Notification record written with status
- **Given** ntfy dispatch succeeds (HTTP 200 from ntfy)
- **When** the notification is sent
- **Then** a `notifications` row exists with `channel="ntfy"`, `status="sent"`, `sent_at=<timestamp>`

### AC3: Failed notification recorded
- **Given** ntfy container is unreachable
- **When** dispatch is attempted
- **Then** `notifications` row written with `status="failed"`, `error="Connection refused"`; no exception propagates to caller

### AC4: Priority mapping correct
- **Given** events with severities `urgent`, `high`, `info`
- **When** each is dispatched
- **Then** ntfy `x-priority` headers are `urgent`, `high`, `default` respectively

### AC5: Test notification endpoint works
- **Given** ntfy is configured
- **When** `POST /api/v1/notifications/test/ntfy` is called
- **Then** a test notification is sent to ntfy; HTTP 200 returned with `{"sent": true}`

---

## Scope

### In Scope
- `netsentry/notifications/ntfy.py` — `NtfyChannel.dispatch()` with httpx PUT
- `netsentry/notifications/engine.py` — `NotificationEngine`: routes to all enabled channels concurrently
- `netsentry/db/repositories/notifications.py` — `NotificationRepository`
- `POST /api/v1/notifications/test/ntfy` endpoint
- `ntfy` service config in `docker-compose.yml` (basic topic, no auth for LAN)
- `NTFY_UPSTREAM_BASE_URL` support for iOS relay

### Out of Scope
- Telegram channel (US0014)
- Apprise (future)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| ntfy returns 429 (rate limited) | Retry once after 5s; if still 429, mark failed |
| ntfy token not configured | Anonymous PUT used; works for self-hosted local ntfy |
| Message body >4096 chars | Truncated to 4096 chars with `...` suffix |
| Deep-link URL contains characters needing encoding | URL-encoded correctly in `x-click` header |

---

## Test Scenarios (TDD)

- [ ] `test_ntfy_dispatch_sends_correct_headers`
- [ ] `test_ntfy_dispatch_writes_sent_notification`
- [ ] `test_ntfy_failure_writes_failed_notification`
- [ ] `test_priority_mapping_urgent_high_info`
- [ ] `test_test_endpoint_returns_200`
- [ ] `test_ios_upstream_relay_header_added`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0012 | Events | Event Engine with dispatch hook | Ready |

## Estimation
**Story Points:** 4
**Complexity:** Medium

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0014: Notification Engine — Telegram Channel

> **Status:** Ready
> **Epic:** [EP0002](../epics/EP0002-deco-integration-notifications.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** to receive Telegram messages when network events occur
**So that** I can use whichever notification app I prefer without being locked into ntfy

## Context

### Background
Implements the Telegram Bot API channel: HTTPS POST to `api.telegram.org/bot{token}/sendMessage` with Markdown-formatted message body and a plain deep-link URL. Bot token from Docker secret; Chat ID from env var. Both ntfy and Telegram can be active simultaneously — the Notification Engine dispatches to all enabled channels concurrently.

---

## Accepted Constraints
- Plain Markdown + deep-link URL only (TRD ADR-006) — no inline keyboard buttons in v1.0
- Bot token stored as Docker secret; never logged

---

## Acceptance Criteria

### AC1: Telegram message sent with correct format
- **Given** Telegram configured with valid Bot token and Chat ID
- **When** a `device.new` event is dispatched
- **Then** `POST https://api.telegram.org/bot{token}/sendMessage` is called with `parse_mode="Markdown"` and body containing `*New Device Detected*`, device name, IP, and `[View Device](http://<host>/devices/<mac>)` link

### AC2: Both channels dispatch concurrently
- **Given** both ntfy and Telegram configured
- **When** an event is dispatched
- **Then** both channels are called concurrently (via `asyncio.gather`); failure of one does not prevent the other

### AC3: Telegram failure recorded independently
- **Given** Telegram API returns 401 (invalid token)
- **When** dispatch is attempted
- **Then** `notifications` row written with `channel="telegram"`, `status="failed"`, `error="401 Unauthorized"`; ntfy dispatch (if configured) is unaffected

### AC4: Telegram disabled when token not configured
- **Given** `TELEGRAM_BOT_TOKEN` not set and `ENABLE_TELEGRAM=false`
- **When** an event fires
- **Then** no Telegram dispatch attempted; no error logged

### AC5: Test notification endpoint works
- **Given** Telegram configured
- **When** `POST /api/v1/notifications/test/telegram` is called
- **Then** a test message is sent; HTTP 200 returned with `{"sent": true}`

---

## Scope

### In Scope
- `netsentry/notifications/telegram.py` — `TelegramChannel.dispatch()` with httpx POST
- Markdown message formatter for each event type
- `POST /api/v1/notifications/test/telegram` endpoint
- `ENABLE_TELEGRAM` feature flag check

### Out of Scope
- Inline keyboard buttons (deferred per ADR-006)
- Bot polling loop

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Telegram API rate limit (429) | Retry after `retry_after` seconds from response; max 1 retry |
| Chat ID not found | 400 response logged as failed; no crash |
| Message >4096 chars (Telegram limit) | Truncated at 4096 chars |
| Bot token contains special characters | URL-encoded in request path |

---

## Test Scenarios (TDD)

- [ ] `test_telegram_dispatch_sends_markdown_message`
- [ ] `test_telegram_includes_deep_link_url`
- [ ] `test_telegram_failure_does_not_affect_ntfy`
- [ ] `test_telegram_disabled_when_not_configured`
- [ ] `test_concurrent_dispatch_to_both_channels`
- [ ] `test_telegram_test_endpoint`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0013 | Notifications | NotificationEngine base | Ready |

## Estimation
**Story Points:** 3
**Complexity:** Low-Medium

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0015: Notification Config API, Settings UI & Deco Topology Panel

> **Status:** Ready
> **Epic:** [EP0002](../epics/EP0002-deco-integration-notifications.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** to configure my notification channels and quiet hours in the dashboard, and see a Deco mesh topology panel
**So that** I can manage alerts and view wireless network structure without editing config files

## Context

### Background
Closes out EP0002 with the user-facing UI elements: notification settings UI (ntfy URL/topic, Telegram token/chat ID, quiet hours, per-alert routing), test notification buttons, and the Deco topology panel showing nodes and connected clients.

---

## Acceptance Criteria

### AC1: GET /api/v1/notifications/config returns current config (redacted)
- **Given** ntfy and Telegram both configured
- **When** `GET /api/v1/notifications/config` is called
- **Then** JSON response shows `{"ntfy": {"configured": true, "url": "http://ntfy:80", "topic": "netsentry"}, "telegram": {"configured": true, "chat_id": "123456789"}}` — tokens not included

### AC2: Settings UI saves notification config
- **Given** user enters ntfy URL and topic in the Settings page
- **When** Save is clicked
- **Then** `PATCH /api/v1/system/config` is called; values persisted in `system_config` table; page shows success toast

### AC3: Test notification button triggers dispatch
- **Given** ntfy configured and the Settings page is open
- **When** user clicks "Send Test" for ntfy
- **Then** `POST /api/v1/notifications/test/ntfy` is called; success/failure feedback shown in UI

### AC4: Deco topology panel shows nodes and clients
- **Given** Deco integration is active with 2 nodes and 10 clients
- **When** the Deco topology panel renders
- **Then** both nodes are shown with client count; each client node shows device name and online status; clicking a client navigates to device detail

### AC5: GET /api/v1/deco/topology returns mesh structure
- **Given** Deco poller has run and populated deco_nodes + mesh_assignments
- **When** `GET /api/v1/deco/topology` is called
- **Then** JSON response: `{"nodes": [{mac, name, role, is_online, client_count}], "clients": [{mac, deco_node_mac, band, is_online}]}`

---

## Scope

### In Scope
- `GET /api/v1/notifications/config`, `GET /api/v1/deco/topology` endpoints
- `PATCH /api/v1/system/config` for non-secret settings (URLs, topics, quiet hours)
- `frontend/src/pages/SettingsPage.tsx` — notification config section
- `frontend/src/components/DecoTopologyPanel.tsx` — node + client display
- Toast notification on save success/failure

### Out of Scope
- Full settings page with all integrations (EP0007)
- Network map with VLAN overlay (EP0007)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| PATCH system/config with unknown key | 400 with error; only whitelisted keys accepted |
| Deco not configured | `GET /api/v1/deco/topology` returns `{"nodes": [], "clients": []}` |
| Test notification fails | UI shows error toast with message from API response |

---

## Test Scenarios (TDD)

- [ ] `test_notifications_config_redacts_tokens`
- [ ] `test_patch_system_config_persists`
- [ ] `test_patch_system_config_rejects_unknown_key`
- [ ] `test_deco_topology_endpoint_returns_structure`
- [ ] `test_deco_topology_empty_when_not_configured`
- [ ] (Vitest) `test_settings_page_saves_ntfy_config`
- [ ] (Vitest) `test_deco_panel_renders_nodes_and_clients`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0013 | Notifications | ntfy channel | Ready |
| US0014 | Notifications | Telegram channel | Ready |
| US0010 | Deco | deco_nodes + mesh_assignments | Ready |

## Estimation
**Story Points:** 5
**Complexity:** Medium — full-stack; both API and React

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |
