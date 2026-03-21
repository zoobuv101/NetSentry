# US0003: SQLite Schema & Alembic Initial Migration

> **Status:** Ready
> **Epic:** [EP0001](../epics/EP0001-foundation-scanner-inventory.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** developer
**I want** all core database tables created by an Alembic migration that runs automatically at startup
**So that** every subsequent story has a stable, versioned schema to read from and write to

## Context

### Background
Creates migration `0001_initial.py` covering all tables needed for EP0001: `devices`, `ip_assignments`, `events`, `scan_runs`, `system_config`, `tags`, `device_tags`, `notifications`, `deletion_audit_log`. The DB connection pool (aiosqlite) and repository base class are also established here. Alembic runs at container startup before FastAPI accepts requests.

---

## Inherited Constraints

| Source | Type | Constraint | AC Implication |
|--------|------|------------|----------------|
| TRD ADR-002 | Data | SQLite + aiosqlite; async throughout | `async with aiosqlite.connect()` pattern; no sync DB calls |
| TRD | Data | ISO-8601 UTC strings for all timestamps | TEXT columns; repository layer parses to `datetime` |
| PRD | Data | MAC address lowercase colon-separated as PK | Normalisation enforced in repository layer, not DB constraint |

---

## Acceptance Criteria

### AC1: Migration runs automatically at startup
- **Given** a fresh SQLite database file (or no file)
- **When** the `netsentry` container starts
- **Then** Alembic runs `upgrade head`, creates the DB file, applies `0001_initial`, and the app starts accepting requests — all within 10 seconds

### AC2: All EP0001 tables created with correct schema
- **Given** the migration has run
- **When** `.tables` is queried via `sqlite3 /data/netsentry.db`
- **Then** all tables exist: `devices`, `ip_assignments`, `events`, `scan_runs`, `system_config`, `tags`, `device_tags`, `notifications`, `deletion_audit_log`, `alembic_version`

### AC3: Migration is idempotent
- **Given** the migration has already run
- **When** the container restarts and Alembic runs `upgrade head` again
- **Then** no error is raised; `alembic current` shows `0001_initial (head)`

### AC4: Repository base class works with async context
- **Given** an async test with an in-memory SQLite DB
- **When** a `BaseRepository.execute("SELECT 1")` is awaited
- **Then** the result is returned without error; no event loop warnings

### AC5: Devices table enforces lifecycle enum
- **Given** the `devices` table exists
- **When** an INSERT with `lifecycle='invalid'` is attempted via the repository
- **Then** a `ValueError` is raised in the Python layer before the DB write (validated in repository, not DB constraint)

### AC6: WAL mode enabled
- **Given** the DB has been created
- **When** `PRAGMA journal_mode` is queried
- **Then** result is `wal`

---

## Scope

### In Scope
- `alembic/versions/0001_initial.py` — all core table DDL
- `netsentry/db/connection.py` — async DB connection factory, WAL mode pragma on first connect
- `netsentry/db/base.py` — `BaseRepository` with `execute()`, `fetchall()`, `fetchone()`, `executemany()`
- Startup hook: `alembic upgrade head` called in FastAPI lifespan before yield
- `netsentry/db/repositories/__init__.py` scaffold

### Out of Scope
- Migration 0002+ (later epics)
- Specific repository implementations (US0004)
- Redis connection (optional, later)

---

## Technical Notes

### WAL mode pragma
```python
async def get_connection(db_path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=OFF")  # enforced in repo layer
    return conn
```

### Alembic startup call
```python
from alembic.config import Config
from alembic import command

def run_migrations(db_path: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
```

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| DB file directory doesn't exist | `FileNotFoundError` caught; logged as CRITICAL; app exits |
| DB file is read-only (permissions) | `OperationalError` caught; logged as CRITICAL; app exits |
| Alembic detects schema mismatch (future) | Upgrade runs; no manual intervention needed |
| Two containers start simultaneously (impossible in this setup but tested) | SQLite WAL handles concurrent access; no corruption |
| `devices.lifecycle` receives invalid value | Repository raises `ValueError("lifecycle must be one of: active, historic, deleted")` |

---

## Test Scenarios (TDD)

- [ ] `test_migration_creates_all_tables` — after `upgrade head`, all expected tables exist
- [ ] `test_migration_idempotent` — running twice raises no error
- [ ] `test_wal_mode_enabled` — PRAGMA journal_mode returns "wal"
- [ ] `test_base_repository_execute` — SELECT 1 returns result
- [ ] `test_base_repository_fetchone_returns_none_on_miss` — fetchone on empty table returns None
- [ ] `test_lifecycle_validation` — invalid lifecycle raises ValueError
- [ ] `test_startup_runs_migration` — FastAPI lifespan triggers migration

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0002 | Predecessor | FastAPI app factory, project scaffold | Ready |

## Estimation
**Story Points:** 4
**Complexity:** Medium — Alembic + async SQLite lifecycle; startup ordering matters

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0004: Device Repository Layer

> **Status:** Ready
> **Epic:** [EP0001](../epics/EP0001-foundation-scanner-inventory.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** developer
**I want** fully-typed async repository classes for devices, IP assignments, events, and scan runs
**So that** every story that touches the database goes through a consistent, tested interface with no raw SQL scattered throughout the codebase

## Context

### Background
Implements `DeviceRepository`, `IpAssignmentRepository`, `EventRepository`, and `ScanRunRepository`. All methods are `async`. MAC addresses are normalised to lowercase colon-separated on write. Timestamps are stored as ISO-8601 UTC strings and returned as `datetime` objects. No story after this one should ever call `aiosqlite` directly.

---

## Inherited Constraints

| Source | Type | Constraint | AC Implication |
|--------|------|------------|----------------|
| TRD | Data | MAC address: lowercase colon-separated | `normalise_mac()` called on every write and lookup |
| TRD | Data | Timestamps: ISO-8601 UTC TEXT in DB; `datetime` in Python | Repository serialises/deserialises on every read/write |
| PRD | Lifecycle | `manually_set` overrides never auto-overwritten | DeviceRepository.update() checks flag before patching identification fields |

---

## Acceptance Criteria

### AC1: DeviceRepository.upsert() creates or updates correctly
- **Given** an empty devices table
- **When** `DeviceRepository.upsert(mac="AA:BB:CC:DD:EE:FF", ip="192.168.1.10", ...)` is awaited
- **Then** a new row is created with `mac_address="aa:bb:cc:dd:ee:ff"` (lowercased), `is_online=1`, `first_seen` and `last_seen` set to current UTC time

### AC2: DeviceRepository.upsert() updates last_seen on second call
- **Given** a device already in the table with `mac="aa:bb:cc:dd:ee:ff"`
- **When** `DeviceRepository.upsert()` is called again with a new IP
- **Then** `last_seen` is updated, `first_seen` is unchanged, `current_ip` is updated to new IP

### AC3: DeviceRepository.list() filters by lifecycle
- **Given** devices with lifecycle `active`, `historic`, and `deleted` in the table
- **When** `DeviceRepository.list(lifecycle="active")` is awaited
- **Then** only the `active` device is returned

### AC4: DeviceRepository.get() returns None for unknown MAC
- **Given** an empty devices table
- **When** `DeviceRepository.get("aa:bb:cc:dd:ee:ff")` is awaited
- **Then** `None` is returned (not an exception)

### AC5: EventRepository.create() writes event and returns ID
- **Given** a device exists in the devices table
- **When** `EventRepository.create(mac_address="aa:bb:cc:dd:ee:ff", event_type="device.new", severity="info", details={})` is awaited
- **Then** an integer `id` is returned and the row is retrievable by that ID

### AC6: ScanRunRepository.start() and complete() lifecycle
- **Given** an empty scan_runs table
- **When** `ScanRunRepository.start(scan_type="arp")` is awaited, then `ScanRunRepository.complete(run_id, devices_found=5)` is awaited
- **Then** the scan_run row has `start` set, `end` set, `devices_found=5`, and `errors` is null

### AC7: MAC normalisation applied consistently
- **Given** repository methods
- **When** any method is called with MAC `"AA-BB-CC-DD-EE-FF"` (dashes, uppercase)
- **Then** it is stored and retrieved as `"aa:bb:cc:dd:ee:ff"`

---

## Scope

### In Scope
- `netsentry/db/repositories/devices.py` — `DeviceRepository`
- `netsentry/db/repositories/ip_assignments.py` — `IpAssignmentRepository`
- `netsentry/db/repositories/events.py` — `EventRepository`
- `netsentry/db/repositories/scan_runs.py` — `ScanRunRepository`
- `netsentry/db/utils.py` — `normalise_mac()`, `utc_now()`, `to_iso8601()`, `from_iso8601()`
- Full type annotations on all public methods; dataclass or Pydantic model return types

### Out of Scope
- IdentificationResult, AvailabilityMonitor, SpeedTestResult repositories (later epics)
- Bulk operations (US0039)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| `upsert()` with invalid lifecycle | `ValueError` raised before DB write |
| `get()` with malformed MAC | `ValueError("Invalid MAC address format")` |
| DB connection dropped mid-transaction | `aiosqlite.OperationalError` propagated to caller |
| `list()` with `limit=0` | Returns empty list, no error |
| `EventRepository.create()` with non-existent MAC | Row created with `mac_address=None` (system events allowed) |
| Concurrent `upsert()` calls for same MAC | SQLite WAL serialises; no duplicate rows; last write wins |

---

## Test Scenarios (TDD)

- [ ] `test_upsert_creates_new_device`
- [ ] `test_upsert_updates_existing_device_last_seen`
- [ ] `test_upsert_preserves_first_seen`
- [ ] `test_list_filters_by_lifecycle`
- [ ] `test_get_returns_none_for_unknown_mac`
- [ ] `test_mac_normalisation_colon_separated_lowercase`
- [ ] `test_mac_normalisation_dashes_to_colons`
- [ ] `test_event_create_returns_id`
- [ ] `test_scan_run_start_complete_lifecycle`
- [ ] `test_ip_assignment_upsert_tracks_source`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0003 | Predecessor | Schema and DB connection factory | Ready |

## Estimation
**Story Points:** 5
**Complexity:** Medium — async patterns throughout; normalisation logic; careful fixture design for tests

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0005: Scanner Engine — ARP Sweep, ICMP Sweep & NetBIOS

> **Status:** Ready
> **Epic:** [EP0001](../epics/EP0001-foundation-scanner-inventory.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** NetSentry to perform ARP sweeps, ICMP ping sweeps, and NetBIOS queries against my configured subnets
**So that** every device on my network is discovered and added to the inventory within one scan cycle

## Context

### Background
Implements the Layer 2 discovery foundation: `arp_sweep()` (arp-scan + scapy ARP), `icmp_sweep()` (fping), and `netbios_scan()` (nbtscan). Each returns a list of `DiscoveredHost` dataclasses. The scanner wraps subprocess tools and handles errors gracefully — a tool failure logs a warning and returns an empty list rather than crashing. Subnet auto-detection from host interfaces is also implemented here.

---

## Inherited Constraints

| Source | Type | Constraint | AC Implication |
|--------|------|------------|----------------|
| PRD NFR | Performance | /24 ARP sweep <30 seconds | ARP sweep must use arp-scan parallel mode, not sequential |
| TRD | Security | `CAP_NET_RAW` required for scapy/ARP | Tests requiring raw sockets must be skipped in non-root CI; use subprocess mock |
| PRD | Scanner | Scan exclusion list: IPs or MACs to skip | `exclusion_list` param on sweep functions |

---

## Acceptance Criteria

### AC1: ARP sweep discovers all hosts in subnet
- **Given** a /24 subnet with 5 known hosts (test network or mocked arp-scan output)
- **When** `arp_sweep(subnet="192.168.1.0/24")` is awaited
- **Then** all 5 hosts are returned as `DiscoveredHost(mac, ip, hostname=None)` within 30 seconds

### AC2: ICMP sweep returns online hosts
- **Given** a subnet where 3 of 5 hosts respond to ICMP
- **When** `icmp_sweep(subnet="192.168.1.0/24")` is awaited
- **Then** exactly 3 `DiscoveredHost` objects are returned

### AC3: Tool failure degrades gracefully
- **Given** `arp-scan` binary is not found (mocked)
- **When** `arp_sweep(subnet="192.168.1.0/24")` is awaited
- **Then** an empty list is returned, a WARNING is logged with the error, and no exception propagates

### AC4: Exclusion list filters results
- **Given** an ARP sweep that would return hosts at `192.168.1.1` and `192.168.1.2`
- **When** `arp_sweep(subnet="...", exclusions={"192.168.1.1"})` is awaited
- **Then** only `192.168.1.2` is in the returned list

### AC5: Subnet auto-detection
- **Given** a host with interface `eth0` at `192.168.1.100/24`
- **When** `detect_subnets()` is called
- **Then** `["192.168.1.0/24"]` is returned (excluding loopback, docker bridges)

### AC6: NetBIOS scan returns Windows hostnames
- **Given** a host responding to NetBIOS at `192.168.1.50` with name `DESKTOP-ABC`
- **When** `netbios_scan(hosts=["192.168.1.50"])` is awaited
- **Then** `DiscoveredHost(mac=None, ip="192.168.1.50", hostname="DESKTOP-ABC")` is returned

---

## Scope

### In Scope
- `netsentry/scanner/arp.py` — `arp_sweep()` wrapping arp-scan subprocess + scapy ARP fallback
- `netsentry/scanner/icmp.py` — `icmp_sweep()` wrapping fping subprocess
- `netsentry/scanner/netbios.py` — `netbios_scan()` wrapping nbtscan subprocess
- `netsentry/scanner/models.py` — `DiscoveredHost` dataclass
- `netsentry/scanner/subnets.py` — `detect_subnets()` using `netifaces` or `/proc/net/if_inet6`
- `netsentry/scanner/utils.py` — subprocess runner with timeout, stderr capture, async executor

### Out of Scope
- TCP port scanning (US0006)
- mDNS/SSDP listeners (US0006)
- APScheduler integration (US0007)
- Writing to DB (US0007 orchestrates that)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Subnet with 0 hosts online | Empty list returned; no error |
| arp-scan returns duplicate MACs (same host, multiple IPs) | Deduplicated by MAC; first IP kept |
| Invalid subnet CIDR (e.g., "999.0.0.0/24") | `ValueError("Invalid subnet CIDR")` raised before subprocess call |
| fping timeout (all hosts offline) | Empty list returned after timeout; no exception |
| nbtscan binary not installed | Empty list + WARNING log |
| Host responds to ICMP but not ARP (cross-VLAN) | Included in ICMP result; MAC is None |
| arp-scan requires root but container has CAP_NET_RAW | Works correctly; CAP_NET_RAW grants raw socket access |

---

## Test Scenarios (TDD)

- [ ] `test_arp_sweep_parses_arp_scan_output` — mock subprocess; verify parsing
- [ ] `test_arp_sweep_tool_failure_returns_empty_list`
- [ ] `test_arp_sweep_respects_exclusion_list`
- [ ] `test_icmp_sweep_parses_fping_output`
- [ ] `test_icmp_sweep_tool_failure_returns_empty_list`
- [ ] `test_netbios_scan_parses_nbtscan_output`
- [ ] `test_detect_subnets_excludes_loopback`
- [ ] `test_detect_subnets_excludes_docker_bridges`
- [ ] `test_discovered_host_mac_normalised`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0001 | Container | CAP_NET_RAW granted | Ready |
| US0002 | Project | Package structure | Ready |

## Estimation
**Story Points:** 5
**Complexity:** Medium — subprocess wrapping with async; multiple tool parsers; CI requires mocking raw socket tools

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0006: Scanner Engine — TCP Port Scan, mDNS/SSDP Listeners & OS Fingerprinting

> **Status:** Ready
> **Epic:** [EP0001](../epics/EP0001-foundation-scanner-inventory.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** NetSentry to probe common TCP ports, passively listen for mDNS/SSDP announcements, and fingerprint operating systems
**So that** each device record is enriched with service information, device type hints, and OS data beyond what ARP and ICMP reveal

## Context

### Background
Adds the remaining scanner capabilities: `tcp_syn_probe()` (nmap SYN scan on common ports), `full_port_scan()` (nmap -p-), `os_fingerprint()` (nmap -O), `service_detect()` (nmap -sV), `mdns_listener()` (scapy multicast), and `ssdp_listener()` (scapy/socket UDP multicast). Listeners are long-lived async tasks, not one-shot scans.

---

## Inherited Constraints

| Source | Type | Constraint | AC Implication |
|--------|------|------------|----------------|
| PRD | Performance | Standard scan (ARP + common ports) <60s | TCP probe must use nmap parallel mode on common port list only |
| TRD | Security | `CAP_NET_RAW` for nmap SYN scan | Tests mock nmap subprocess |
| PRD | Scanner | Common ports: 22, 80, 443, 8080, 8443, 554, 1883 (and ~20 others) | Port list configurable; default list in `config.py` |

---

## Acceptance Criteria

### AC1: TCP SYN probe returns open ports per host
- **Given** a host at `192.168.1.10` with ports 22 and 80 open
- **When** `tcp_syn_probe(hosts=["192.168.1.10"], ports=[22, 80, 443])` is awaited
- **Then** returns `{ip: "192.168.1.10", open_ports: [22, 80]}` within 60 seconds for the full default list

### AC2: OS fingerprint returns OS family
- **Given** a host running Linux
- **When** `os_fingerprint(host="192.168.1.10")` is awaited
- **Then** returns `OsFingerprint(os_family="Linux", os_version="5.x", confidence=0.85)` or `None` if inconclusive

### AC3: mDNS listener captures service announcements
- **Given** the mDNS listener is running
- **When** an Apple device broadcasts `_airplay._tcp.local` mDNS record
- **Then** `MdnsRecord(ip="192.168.1.20", service_type="_airplay._tcp", name="Living Room TV")` is emitted via callback

### AC4: SSDP listener captures UPnP device type
- **Given** the SSDP listener is running
- **When** a smart TV sends a SSDP NOTIFY with `deviceType: urn:schemas-upnp-org:device:MediaRenderer:1`
- **Then** `SsdpRecord(ip="192.168.1.30", device_type="MediaRenderer", usn="...")` is emitted via callback

### AC5: nmap failure degrades gracefully
- **Given** nmap binary not available (mocked)
- **When** `tcp_syn_probe()` is awaited
- **Then** empty port list returned; WARNING logged; no exception

### AC6: Service detection returns version strings
- **Given** port 22 open on a host running OpenSSH 8.9
- **When** `service_detect(host="192.168.1.10", ports=[22])` is awaited
- **Then** returns `[ServiceRecord(port=22, protocol="tcp", service="ssh", version="OpenSSH 8.9")]`

---

## Scope

### In Scope
- `netsentry/scanner/tcp.py` — `tcp_syn_probe()`, `full_port_scan()`, `service_detect()` via python-nmap
- `netsentry/scanner/os_detect.py` — `os_fingerprint()` via nmap -O
- `netsentry/scanner/mdns.py` — `mdns_listener()` async task using scapy multicast sniff
- `netsentry/scanner/ssdp.py` — `ssdp_listener()` async task on UDP 1900
- `netsentry/scanner/models.py` — extended with `PortScanResult`, `OsFingerprint`, `ServiceRecord`, `MdnsRecord`, `SsdpRecord`

### Out of Scope
- Writing scan results to DB (US0007)
- Device identification from port patterns (EP0004)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Host goes offline between ARP sweep and port scan | nmap returns no results; host marked offline (handled in US0007) |
| mDNS listener receives malformed packet | Exception caught per-packet; listener continues |
| SSDP listener floods with high-volume announcements | Per-IP rate limiting in listener (max 10 records/IP/minute) |
| nmap -O requires root but CAP_NET_RAW present | Works; CAP_NET_RAW sufficient for SYN scan and OS fingerprint |
| Full port scan (65535 ports) takes >5 minutes | Runs in background; does not block standard scan cycle |

---

## Test Scenarios (TDD)

- [ ] `test_tcp_probe_parses_nmap_xml_output`
- [ ] `test_tcp_probe_tool_failure_returns_empty`
- [ ] `test_os_fingerprint_parses_nmap_os_output`
- [ ] `test_os_fingerprint_returns_none_when_inconclusive`
- [ ] `test_mdns_listener_emits_callback_on_record`
- [ ] `test_ssdp_listener_parses_notify_packet`
- [ ] `test_service_detect_returns_version_string`
- [ ] `test_ssdp_rate_limiter_prevents_flood`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0005 | Scanner | DiscoveredHost model; subnet detection | Ready |

## Estimation
**Story Points:** 6
**Complexity:** High — multiple async listeners; subprocess nmap wrapping; multicast socket handling in tests

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0007: APScheduler Task Harness, Scan Profiles & OUI Resolution

> **Status:** Ready
> **Epic:** [EP0001](../epics/EP0001-foundation-scanner-inventory.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** NetSentry to automatically run scans on a schedule, write results to the device inventory, and resolve MAC vendor information
**So that** my device list stays current without any manual intervention

## Context

### Background
Wires together all scanner components (US0005, US0006) with APScheduler, the device repository (US0004), and the OUI database. Implements the three scan profiles (Quick, Standard, Deep), the online/offline state machine (offline after N missed cycles), and the Enrichment Engine's first pass (merge scan results into device records, create Events for new devices). OUI resolution from the Wireshark manuf file is also implemented here.

---

## Inherited Constraints

| Source | Type | Constraint | AC Implication |
|--------|------|------------|----------------|
| PRD | Business logic | Device offline after 2 consecutive missed cycles (configurable) | `missed_cycles` counter per device in DB or in-memory |
| PRD | Scanner | On-demand scan trigger via API | `POST /api/v1/scan/trigger` must start scan within 2 seconds |
| TRD ADR-007 | Architecture | APScheduler `AsyncIOScheduler`; tasks are async coroutines | All scan tasks `async def`; no blocking calls |

---

## Acceptance Criteria

### AC1: ARP scan scheduled and runs automatically
- **Given** `SCAN_INTERVAL_ARP=300` (5 minutes)
- **When** the scheduler starts
- **Then** `arp_sweep()` is called at startup and every 300 seconds thereafter; results are written to `devices` and `ip_assignments` tables

### AC2: New device creates a `device.new` Event
- **Given** no devices in the inventory
- **When** ARP sweep discovers a host at `192.168.1.50` with MAC `aa:bb:cc:dd:ee:ff`
- **Then** a new device row is created AND an Event `{event_type: "device.new", severity: "urgent", mac_address: "aa:bb:cc:dd:ee:ff"}` is written to the events table

### AC3: Device marked offline after N missed cycles
- **Given** a device `aa:bb:cc:dd:ee:ff` is in the inventory with `is_online=1`
- **When** 2 consecutive ARP scans complete without seeing this MAC (default threshold)
- **Then** `is_online` is set to `0` and a `device.offline` Event is created

### AC4: Scan profiles execute correct tool subset
- **Given** a `POST /api/v1/scan/trigger` with `{"profile": "quick"}`
- **When** the scan runs
- **Then** only ARP sweep and ICMP sweep are called; TCP probe and OS fingerprint are NOT called

### AC5: OUI vendor resolved from manuf file
- **Given** the Wireshark manuf file is loaded
- **When** `resolve_vendor("aa:bb:cc:00:00:00")` is called
- **Then** the manufacturer string for the OUI `aa:bb:cc` is returned within 1ms (in-memory lookup)

### AC6: Weekly OUI refresh runs without restart
- **Given** the scheduler is running
- **When** the weekly OUI refresh job fires (or is triggered manually)
- **Then** the manuf file is downloaded from the Wireshark URL and the in-memory lookup is updated atomically; no request failures during refresh

### AC7: On-demand scan trigger responds within 2 seconds
- **Given** the API is running and no scan is in progress
- **When** `POST /api/v1/scan/trigger {"profile": "standard"}` is called
- **Then** HTTP 202 is returned within 2 seconds; the scan starts asynchronously

---

## Scope

### In Scope
- `netsentry/scanner/orchestrator.py` — `ScanOrchestrator`: coordinates sweep → enrich → store pipeline
- `netsentry/scanner/oui.py` — OUI database loader, in-memory trie/dict lookup, weekly refresh
- `netsentry/core/scheduler.py` — APScheduler `AsyncIOScheduler` lifecycle; job registration
- `netsentry/scanner/profiles.py` — `ScanProfile` enum (Quick, Standard, Deep) and tool selection logic
- `netsentry/events/engine.py` — `EventEngine.emit()` for device.new, device.offline events (stub for notification dispatch — wired in EP0002)
- `POST /api/v1/scan/trigger` endpoint, `GET /api/v1/scan/status` endpoint
- `missed_cycles` tracking (stored in `system_config` or in-memory; reset on device seen)

### Out of Scope
- Notification dispatch (EP0002)
- Integration pollers (EP0002/EP0003)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Scan already running when trigger received | Returns 409 with `{"error": {"code": "SCAN_IN_PROGRESS"}}` |
| OUI file download fails | Previous cached file retained; WARNING logged; retry next scheduled refresh |
| Scheduler job throws unhandled exception | APScheduler logs exception; job rescheduled on next interval |
| Device reappears after being marked offline | `is_online` set to 1; `device.online` Event created |
| `SCAN_SUBNETS` env var not set | `detect_subnets()` used; auto-detected subnets logged at INFO |

---

## Test Scenarios (TDD)

- [ ] `test_new_device_creates_event`
- [ ] `test_offline_after_n_missed_cycles`
- [ ] `test_device_online_event_on_reappearance`
- [ ] `test_quick_profile_only_calls_arp_and_icmp`
- [ ] `test_standard_profile_calls_tcp_probe`
- [ ] `test_oui_lookup_returns_vendor`
- [ ] `test_oui_lookup_unknown_mac_returns_none`
- [ ] `test_scan_trigger_returns_202`
- [ ] `test_scan_trigger_409_when_scan_running`
- [ ] `test_scheduler_registers_arp_job_on_startup`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0004 | Data | Device repository | Ready |
| US0005 | Scanner | ARP/ICMP/NetBIOS sweeps | Ready |
| US0006 | Scanner | TCP probe, mDNS, OS fingerprint | Ready |

## Estimation
**Story Points:** 7
**Complexity:** High — wires all components; state machine for online/offline; APScheduler lifecycle in tests is tricky

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |

---
---
---

# US0008: FastAPI Device Endpoints & React Device Table Scaffold

> **Status:** Ready
> **Epic:** [EP0001](../epics/EP0001-foundation-scanner-inventory.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** network operator
**I want** a web page showing all discovered devices in a table with key fields visible
**So that** I can see my network inventory without using the command line or API directly

## Context

### Background
Completes EP0001 with the REST endpoints that the frontend consumes (`GET /api/v1/devices`, `GET /api/v1/devices/{mac}`) and a minimal React SPA: device table with columns for friendly name (or hostname), IP, MAC, vendor, online status badge, and last seen. The frontend is served via FastAPI StaticFiles. React polling of the device list at 10s intervals is included.

---

## Inherited Constraints

| Source | Type | Constraint | AC Implication |
|--------|------|------------|----------------|
| TRD ADR-003 | Frontend | FastAPI serves React build via StaticFiles | Vite build output copied into container; StaticFiles mount |
| PRD NFR | API | `GET /devices` <200ms for 200 devices | Repository query must use index on `lifecycle`; no N+1 queries |
| PRD | UX | Responsive layout | Tailwind responsive breakpoints on table |

---

## Acceptance Criteria

### AC1: GET /api/v1/devices returns device list
- **Given** 5 devices in the inventory (3 active, 1 historic, 1 deleted)
- **When** `GET /api/v1/devices` is called
- **Then** HTTP 200 with JSON array of 3 active devices; each has `mac_address`, `current_ip`, `hostname`, `vendor`, `is_online`, `last_seen`, `category`, `owner`, `friendly_name`

### AC2: GET /api/v1/devices?lifecycle=historic returns archived devices
- **Given** 1 historic device in inventory
- **When** `GET /api/v1/devices?lifecycle=historic` is called
- **Then** HTTP 200 with array containing only the historic device

### AC3: GET /api/v1/devices/{mac} returns full device detail
- **Given** a device `aa:bb:cc:dd:ee:ff` with IP assignments and events
- **When** `GET /api/v1/devices/aa:bb:cc:dd:ee:ff` is called
- **Then** HTTP 200 with device object including `ip_history` array and `recent_events` array (last 10)

### AC4: GET /api/v1/devices/{mac} returns 404 for unknown MAC
- **Given** no device with MAC `ff:ee:dd:cc:bb:aa`
- **When** `GET /api/v1/devices/ff:ee:dd:cc:bb:aa` is called
- **Then** HTTP 404 with `{"error": {"code": "DEVICE_NOT_FOUND", "message": "..."}}`

### AC5: React device table renders and polls
- **Given** the frontend is loaded in a browser
- **When** the page loads
- **Then** a table is displayed with columns: Name, IP, MAC, Vendor, Status (badge: green Online / grey Offline), Last Seen; data fetched from `GET /api/v1/devices`

### AC6: Device table updates without page reload
- **Given** the table is rendered and polling every 10 seconds
- **When** a new device is added to the DB (simulated by direct INSERT)
- **Then** the new device appears in the table within 15 seconds without a full page refresh

### AC7: API response time under 200ms
- **Given** 200 devices in the inventory
- **When** `GET /api/v1/devices` is called
- **Then** response time is <200ms (measured via pytest benchmark or httpx timing)

---

## Scope

### In Scope
- `netsentry/api/v1/devices.py` — `GET /devices`, `GET /devices/{mac}` endpoints with Pydantic response models
- `DeviceResponse`, `DeviceDetailResponse` Pydantic schemas
- `GET /api/v1/devices` supports `?lifecycle=` filter and `?limit=` param (default 500)
- React scaffold: `frontend/src/App.tsx`, `frontend/src/pages/DevicesPage.tsx`, `frontend/src/components/DeviceTable.tsx`
- Tailwind + shadcn/ui Table component
- `useDevices()` hook with 10s polling interval
- FastAPI `StaticFiles` mount of `frontend/dist/`
- Vite build configuration; `pnpm build` produces `frontend/dist/`
- Dockerfile multi-stage: Node build stage → Python runtime stage

### Out of Scope
- PATCH/DELETE endpoints (EP0004)
- Device detail page full (EP0007)
- Category/owner columns (EP0004)

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| `GET /devices` with empty inventory | Returns HTTP 200 with empty array `[]` |
| MAC in URL with uppercase | Normalised to lowercase before lookup; correct device returned |
| MAC in URL with dashes | Normalised to colons; correct device returned |
| React fetch fails (API down) | Error state displayed in table with retry button |
| 200 devices response >200ms | Investigated; index added on `devices.lifecycle` column |
| Frontend build not present | FastAPI returns 404 for `/`; API still works |

---

## Test Scenarios (TDD)

- [ ] `test_get_devices_returns_active_only_by_default`
- [ ] `test_get_devices_lifecycle_historic_filter`
- [ ] `test_get_devices_empty_inventory_returns_empty_array`
- [ ] `test_get_device_detail_includes_ip_history`
- [ ] `test_get_device_404_for_unknown_mac`
- [ ] `test_mac_normalisation_in_url_path`
- [ ] `test_get_devices_response_time_200_devices` (benchmark)
- [ ] `test_device_response_schema_fields_present`
- [ ] (Vitest) `test_device_table_renders_device_rows`
- [ ] (Vitest) `test_device_table_shows_online_badge`

---

## Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0004 | Data | Device repository | Ready |
| US0007 | Scanner | Devices in DB from scan | Ready |

## Estimation
**Story Points:** 6
**Complexity:** Medium — full-stack story; React + FastAPI; Docker multi-stage build

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |
