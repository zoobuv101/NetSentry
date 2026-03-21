# US0016: pfSense REST API Client

> **Status:** Ready
> **Epic:** [EP0003](../epics/EP0003-pfsense-adguard-integrations.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** developer
**I want** a typed pfSense REST API client that handles authentication, API version detection, and error handling
**So that** all pfSense data polling has a reliable, tested foundation

## Context

### Background
Implements `PfSenseRestClient` wrapping pfrest.org v2 API (v1 fallback). Bearer token from Docker secret. Auto-detects API version at startup by attempting a v2 endpoint; falls back to v1 if 404. All HTTP calls use httpx with configurable timeout and retry logic.

---

## Acceptance Criteria

### AC1: Client authenticates with Bearer token
- **Given** valid API key configured as Docker secret
- **When** any request is made
- **Then** `Authorization: Bearer <key>` header is included in every request

### AC2: API version auto-detected
- **Given** pfSense with REST API v2 installed
- **When** `PfSenseRestClient.detect_version()` is called
- **Then** `api_version=2` is stored; all subsequent requests use `/api/v2/` prefix

### AC3: v1 fallback on v2 404
- **Given** pfSense with only REST API v1 installed
- **When** `detect_version()` calls a v2 endpoint and receives 404
- **Then** `api_version=1` stored; `/api/v1/` prefix used

### AC4: Connection error raises `PfSenseConnectionError`
- **Given** pfSense IP unreachable
- **When** any request is made
- **Then** `PfSenseConnectionError` raised after 10s timeout

### AC5: Authentication failure raises `PfSenseAuthError`
- **Given** invalid API key
- **When** any request is made
- **Then** `PfSenseAuthError` raised on 401/403 response

---

## Scope

### In Scope
- `netsentry/integrations/pfsense/client.py` — `PfSenseRestClient`
- `netsentry/integrations/pfsense/exceptions.py`
- Version detection and prefix management

### Out of Scope
- SSH fallback (US0017)
- Data polling (US0018)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| SSL cert validation fails (self-signed) | `verify=False` used by default; `PFSENSE_VERIFY_SSL=true` opt-in |
| Request returns 500 | `PfSenseServerError` raised with response body |
| Version detection timeout | Defaults to v2; logs WARNING |

---

## Test Scenarios (TDD)

- [ ] `test_bearer_token_in_every_request`
- [ ] `test_v2_version_detection`
- [ ] `test_v1_fallback_on_404`
- [ ] `test_connection_error_raises`
- [ ] `test_auth_failure_raises`
- [ ] `test_ssl_verify_disabled_by_default`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0002 | Project | httpx, project scaffold | Ready |

## Estimation
**Story Points:** 3 | **Complexity:** Low-Medium

---

# US0017: pfSense SSH Fallback Client

> **Status:** Ready
> **Epic:** [EP0003](../epics/EP0003-pfsense-adguard-integrations.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** developer
**I want** an SSH-based fallback client for pfSense using the existing pfsense_proxy.py pattern
**So that** critical pfSense data (DNS resolver cache) is still accessible when the REST API is unavailable

## Context

### Background
Reuses the `pfsense_proxy.py` SSH pattern from the existing FW_agent project (paramiko-based). Implements `PfSenseSshClient` with `execute_command()` wrapping paramiko `SSHClient`. Triggered automatically by the poller when `PfSenseRestClient` raises `PfSenseConnectionError` for two consecutive polls.

---

## Acceptance Criteria

### AC1: SSH client executes command and returns output
- **Given** valid SSH credentials configured
- **When** `PfSenseSshClient.execute("unbound-control dump_cache")` is awaited
- **Then** stdout is returned as string; no exception

### AC2: SSH fallback activates on REST failure
- **Given** `PfSenseRestClient` raises `PfSenseConnectionError` for 2 consecutive polls
- **When** the next poll runs
- **Then** `PfSenseSshClient.execute()` is called for SSH-accessible data; WARNING logged

### AC3: SSH failure raises `PfSenseSshError`
- **Given** SSH credentials invalid or host unreachable
- **When** `execute()` is called
- **Then** `PfSenseSshError` raised; poller marks integration as unhealthy

### AC4: SSH client cleans up connection on error
- **Given** an SSH connection is established
- **When** any exception occurs during command execution
- **Then** the paramiko connection is closed in a `finally` block; no connection leak

---

## Scope

### In Scope
- `netsentry/integrations/pfsense/ssh_client.py` — `PfSenseSshClient`
- `netsentry/integrations/pfsense/fallback.py` — fallback activation logic (2-failure threshold)

### Out of Scope
- Data parsing from SSH output (US0018)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| SSH host key not in known_hosts | `AutoAddPolicy` used; WARNING logged |
| Command times out (30s default) | `PfSenseSshError("Command timed out")` |
| REST API recovers after SSH fallback | REST client re-tried on next poll; SSH fallback deactivated |

---

## Test Scenarios (TDD)

- [ ] `test_ssh_executes_command_returns_stdout`
- [ ] `test_ssh_fallback_activates_after_2_rest_failures`
- [ ] `test_ssh_failure_raises_error`
- [ ] `test_ssh_connection_closed_on_exception`
- [ ] `test_rest_recovery_deactivates_fallback`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0016 | Integration | PfSenseRestClient | Ready |

## Estimation
**Story Points:** 3 | **Complexity:** Medium

---

# US0018: pfSense Poller — DHCP, ARP, States, Rules & Device Enrichment

> **Status:** Ready
> **Epic:** [EP0003](../epics/EP0003-pfsense-adguard-integrations.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** NetSentry to pull DHCP leases, ARP table, firewall states, and interface data from pfSense every 30 seconds
**So that** every device record shows its hostname, VLAN, traffic stats, and firewall rule membership from the authoritative source

## Context

### Background
Implements the pfSense poller APScheduler job. Polls DHCP leases (`/api/v2/services/dhcp_server/leases`), ARP table (`/api/v2/diagnostics/arp`), firewall states (`/api/v2/diagnostics/states`), firewall rules (`/api/v2/firewall/rules`), and interface data (`/api/v2/interface`). Enriches device records. Writes to `traffic_samples` table (Alembic migration 0003).

---

## Acceptance Criteria

### AC1: DHCP hostname written to device record
- **Given** pfSense DHCP lease for MAC `aa:bb:cc:dd:ee:ff` with hostname `my-laptop`
- **When** poller runs
- **Then** `devices.hostname="my-laptop"` and an `ip_assignments` row with `source="dhcp"` exists

### AC2: Traffic stats written to traffic_samples
- **Given** pfSense reports device `192.168.1.10` with 1024 bytes in, 2048 bytes out, 3 connections
- **When** poller runs
- **Then** `traffic_samples` row for `aa:bb:cc:dd:ee:ff` with correct values and current timestamp

### AC3: VLAN extracted from interface data
- **Given** pfSense interface `opt2` is VLAN 30 and device `192.168.1.x` is on this interface
- **When** poller runs
- **Then** `devices` row updated with `vlan_id=30`

### AC4: Firewall rule references stored
- **Given** a firewall rule references the alias containing device IP
- **When** poller runs
- **Then** rule reference stored in device detail (JSON blob in `devices.firewall_rules_json`)

### AC5: ARP table cross-references Deco UNKNOWN IPs
- **Given** Deco reports device MAC `aa:bb:cc:dd:ee:ff` with IP "UNKNOWN"
- **And** pfSense ARP table maps this MAC to `192.168.1.55`
- **When** poller runs
- **Then** `ip_assignments` updated with correct IP; Deco mesh_assignment `last_known_ip` updated

### AC6: Poller degrades gracefully on failure
- **Given** pfSense REST raises `PfSenseConnectionError`
- **When** poller job runs
- **Then** WARNING logged; existing device enrichment data unchanged; SSH fallback attempted (US0017)

---

## Scope

### In Scope
- Alembic migration `0003_pfsense.py` — `traffic_samples` table; `vlan_id`, `firewall_rules_json` columns on `devices`
- `netsentry/integrations/pfsense/poller.py` — `PfSensePoller`
- `netsentry/db/repositories/traffic.py` — `TrafficSampleRepository`
- Poller registered in APScheduler at 30s interval

### Out of Scope
- Gateway alerting (US0019)
- AdGuard (US0020/US0021)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Device in pfSense ARP but not in inventory | Device added to inventory with `source="pfsense_arp"` |
| DHCP lease for MAC not in inventory | Device created with hostname and DHCP IP |
| Firewall states table is very large (1000+ entries) | Aggregate by source IP; do not store raw state dump |
| VLAN data missing from interface response | `vlan_id` remains NULL; no error |

---

## Test Scenarios (TDD)

- [ ] `test_dhcp_hostname_written_to_device`
- [ ] `test_traffic_sample_written`
- [ ] `test_vlan_extracted_from_interface`
- [ ] `test_arp_resolves_deco_unknown_ip`
- [ ] `test_graceful_degradation_on_rest_failure`
- [ ] `test_new_device_created_from_arp`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0016 | Integration | PfSenseRestClient | Ready |
| US0017 | Integration | SSH fallback | Ready |
| US0004 | Data | Device repository | Ready |

## Estimation
**Story Points:** 6 | **Complexity:** High — multiple endpoints; cross-reference logic; large response normalisation

---

# US0019: pfSense Gateway Alerting, Status API & Dashboard Panel

> **Status:** Ready
> **Epic:** [EP0003](../epics/EP0003-pfsense-adguard-integrations.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** to be alerted when my WAN gateway goes down and to see pfSense health in the dashboard
**So that** I know immediately when my internet connection fails

## Context

### Background
Polls pfSense gateway status and system info. Emits `pfsense.wan_down` (urgent) and `pfsense.unreachable` events. Exposes `GET /api/v1/pfsense/status`. Adds pfSense status panel to dashboard.

---

## Acceptance Criteria

### AC1: WAN down alert fires within 60 seconds
- **Given** pfSense gateway status transitions from `online` to `down`
- **When** the poller detects this change
- **Then** `pfsense.wan_down` event with `severity="urgent"` is emitted; notification dispatched

### AC2: pfSense unreachable alert
- **Given** pfSense REST + SSH both fail for 2 consecutive polls
- **When** the third poll fails
- **Then** `pfsense.unreachable` event emitted

### AC3: GET /api/v1/pfsense/status returns gateway and system info
- **Given** pfSense is reachable
- **When** `GET /api/v1/pfsense/status` is called
- **Then** HTTP 200 with `{"gateway": {"name", "status", "latency_ms"}, "system": {"uptime", "cpu_pct", "mem_pct", "version"}}`

### AC4: Dashboard pfSense panel renders status
- **Given** pfSense configured and reachable
- **When** dashboard loads
- **Then** pfSense status panel shows gateway name, status (green/red), latency, and pfSense version

### AC5: WAN recovery alert
- **Given** gateway was `down` and has recovered
- **When** next poller detects `online` status
- **Then** `pfsense.wan_recovered` event emitted; notification dispatched

---

## Scope

### In Scope
- Gateway status polling (30s interval via existing pfSense poller)
- `pfsense.wan_down`, `pfsense.wan_recovered`, `pfsense.unreachable` event types
- `GET /api/v1/pfsense/status` endpoint
- `frontend/src/components/PfSenseStatusPanel.tsx`
- Gateway state stored in `system_config` for change detection

### Out of Scope
- pfSense config management
- Firewall rule display UI (EP0007)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Multiple WAN gateways | All gateways polled; alert per gateway |
| Gateway latency only increases (no full down) | No alert; latency tracked in traffic_samples |
| pfSense reachable but gateway data missing | Logged as WARNING; no false alert |

---

## Test Scenarios (TDD)

- [ ] `test_wan_down_event_emitted_on_status_change`
- [ ] `test_wan_recovery_event`
- [ ] `test_pfsense_unreachable_after_2_consecutive_failures`
- [ ] `test_pfsense_status_endpoint`
- [ ] (Vitest) `test_pfsense_panel_renders_gateway_status`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0018 | Integration | pfSense poller base | Ready |
| US0012 | Events | Event Engine | Ready |

## Estimation
**Story Points:** 4 | **Complexity:** Medium

---

# US0020: AdGuard Home Client, Poller & DNS Profile Storage

> **Status:** Ready
> **Epic:** [EP0003](../epics/EP0003-pfsense-adguard-integrations.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** NetSentry to poll AdGuard Home and show per-device DNS profiles
**So that** I can see what domains each device is querying and how many are being blocked

## Context

### Background
Implements AdGuard Home REST client (Basic Auth), poller (60s interval), and `dns_profiles` Alembic migration. Query log is polled for recent entries only (last 2× poll interval) and aggregated into hourly DNS profile records per device.

---

## Acceptance Criteria

### AC1: AdGuard client authenticates with Basic Auth
- **Given** valid AdGuard credentials in Docker secrets
- **When** any request is made
- **Then** `Authorization: Basic <b64(user:pass)>` header present

### AC2: Per-device DNS profile aggregated and stored
- **Given** AdGuard query log with 50 queries from `192.168.1.10` (40 allowed, 10 blocked)
- **When** poller runs
- **Then** `dns_profiles` row for the device's MAC with `query_count=50`, `blocked_count=10`, `top_domains=[...]` for the current hour

### AC3: IP-to-MAC mapping applied to DNS profiles
- **Given** AdGuard query from `192.168.1.10` and device `aa:bb:cc:dd:ee:ff` has this IP in `ip_assignments`
- **When** poller aggregates queries
- **Then** `dns_profiles.mac_address="aa:bb:cc:dd:ee:ff"` (not IP)

### AC4: Suspicious query flag set
- **Given** a device makes >500 DNS queries in one hour (configurable threshold)
- **When** the hourly aggregate is computed
- **Then** `dns_profiles.suspicious=True`; `adguard.suspicious_queries` Event created

### AC5: Graceful degradation on AdGuard unreachable
- **Given** AdGuard returns connection error
- **When** poller runs
- **Then** WARNING logged; existing dns_profiles unchanged; no crash

---

## Scope

### In Scope
- Alembic migration `0004_adguard.py` — `dns_profiles` table
- `netsentry/integrations/adguard/client.py` — `AdGuardClient` with Basic Auth
- `netsentry/integrations/adguard/poller.py` — `AdGuardPoller` APScheduler 60s job
- `netsentry/db/repositories/dns_profiles.py` — `DnsProfileRepository`
- IP→MAC resolution using `ip_assignments` table

### Out of Scope
- AdGuard status API and dashboard panel (US0021)
- DNS patterns as identification signal (EP0004 US0023)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Device IP not in ip_assignments | DNS profile stored with IP only; `mac_address=NULL`; linked later when device discovered |
| Query log returns thousands of entries | Paginate or filter to last N minutes; aggregate in Python |
| AdGuard returns 401 | `AdGuardAuthError` raised; integration marked unhealthy |

---

## Test Scenarios (TDD)

- [ ] `test_basic_auth_in_requests`
- [ ] `test_dns_profile_aggregation`
- [ ] `test_ip_to_mac_mapping`
- [ ] `test_suspicious_query_flag`
- [ ] `test_graceful_degradation`
- [ ] `test_hourly_aggregation_creates_new_row`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0004 | Data | ip_assignments repository | Ready |

## Estimation
**Story Points:** 5 | **Complexity:** Medium-High — IP→MAC mapping; aggregation logic

---

# US0021: AdGuard Status API, Dashboard Panel & Device DNS Tab

> **Status:** Ready
> **Epic:** [EP0003](../epics/EP0003-pfsense-adguard-integrations.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** to see AdGuard Home stats in the dashboard and per-device DNS profiles in the device detail page
**So that** I can understand my network's DNS health and each device's querying behaviour

## Context

### Background
Exposes AdGuard data via REST API and wires up the frontend: global AdGuard status panel (filter status, top blocked domains, total query stats) and a DNS tab in the device detail page (top domains, blocked count, query volume chart).

---

## Acceptance Criteria

### AC1: GET /api/v1/adguard/status returns filter and query stats
- **Given** AdGuard is configured and poller has run
- **When** `GET /api/v1/adguard/status` is called
- **Then** HTTP 200 with `{"total_queries": N, "blocked_queries": N, "blocked_pct": N, "top_blocked_domains": [...], "filter_count": N, "dnssec_enabled": bool}`

### AC2: GET /api/v1/devices/{mac}/dns returns device DNS profile
- **Given** device `aa:bb:cc:dd:ee:ff` has dns_profiles records
- **When** `GET /api/v1/devices/aa:bb:cc:dd:ee:ff/dns` is called
- **Then** HTTP 200 with `{"total_queries_24h": N, "blocked_24h": N, "blocked_pct": N, "top_domains": [...], "hourly_history": [...]}`

### AC3: Dashboard AdGuard panel renders
- **Given** AdGuard configured
- **When** dashboard loads
- **Then** AdGuard panel shows total queries, blocked %, and top 5 blocked domains

### AC4: Device detail DNS tab renders
- **Given** device has dns_profiles data
- **When** DNS tab is selected on device detail page
- **Then** top queried domains table shown; blocked count and percentage displayed; suspicious flag highlighted if set

### AC5: AdGuard not configured returns 503
- **Given** `ENABLE_ADGUARD_INTEGRATION=false`
- **When** `GET /api/v1/adguard/status` is called
- **Then** HTTP 503 with `{"error": {"code": "INTEGRATION_DISABLED"}}`

---

## Scope

### In Scope
- `GET /api/v1/adguard/status`, `GET /api/v1/devices/{mac}/dns` endpoints
- `frontend/src/components/AdGuardStatusPanel.tsx`
- DNS tab in device detail (scaffold only; full detail page in EP0007 US0040/US0041)

### Out of Scope
- Full device detail page (EP0007)
- DNS identification signal feeding (EP0004)

---

## Test Scenarios (TDD)

- [ ] `test_adguard_status_endpoint`
- [ ] `test_device_dns_endpoint`
- [ ] `test_adguard_disabled_returns_503`
- [ ] `test_device_dns_returns_404_unknown_mac`
- [ ] (Vitest) `test_adguard_panel_renders_stats`
- [ ] (Vitest) `test_device_dns_tab_renders_domains`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0020 | Integration | AdGuard poller + dns_profiles | Ready |
| US0008 | Frontend | Device detail page scaffold | Ready |

## Estimation
**Story Points:** 4 | **Complexity:** Medium

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft — all EP0003 stories |
