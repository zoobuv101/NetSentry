# Product Requirements Document

**Project:** NetSentry
**Version:** 1.1
**Last Updated:** 2026-03-21
**Status:** Draft

---

## 1. Project Overview

### Product Name
NetSentry — Self-Hosted Network Intelligence Platform

### Purpose
NetSentry is a self-hosted, containerised network intelligence platform designed to run continuously on a home network. It combines the device discovery and monitoring capabilities of commercial tools like Fing with deep integration into pfSense firewalls, TP-Link Deco mesh systems, and AdGuard Home DNS servers, providing a unified, privacy-first view of every device, connection, and DNS query on the network. All data remains on-premises with no cloud dependency and no recurring costs. NetSentry actively identifies new devices using multi-source fingerprinting and optional AI enrichment, monitors device availability in real time, tracks internet speed over time, and sends alerts via ntfy, Telegram, or other channels.

### Tech Stack
- **Backend:** Python 3.12+, FastAPI, APScheduler, aiosqlite
- **Scanning:** nmap, arp-scan, scapy, fping
- **Mesh Integration:** Custom Python client (reverse-engineered Deco local API, based on ha-tplink-deco)
- **Frontend:** React 18 + TypeScript + Vite, shadcn/ui + Tailwind CSS
- **Database:** SQLite (primary), Redis (optional cache)
- **Push Notifications:** ntfy (binwiederhier/ntfy), Telegram Bot API, Apprise (multi-channel secondary)
- **AI Enrichment:** Anthropic Claude API (optional, for device identification assistance)
- **Speed Testing:** speedtest-cli / librespeed-cli
- **Containerisation:** Docker + Docker Compose
- **OUI Database:** Wireshark manuf file

### Architecture Pattern
Event-driven microservice stack deployed as Docker Compose. A central Scanner Engine performs active network discovery on a configurable schedule. Multiple integration pollers (Deco, pfSense, AdGuard) run as APScheduler tasks. An Enrichment Engine merges all data sources — including optional AI classification — into a unified device record stored in SQLite. A real-time Availability Monitor polls specified devices on a tight interval independently of the main scan cycle. An Internet Speed Monitor runs scheduled speed tests and stores results. A FastAPI REST server exposes all data to a React SPA. Events trigger push notifications via ntfy, Telegram, or Apprise. The entire stack runs on a single Docker host with host networking for Layer 2 ARP scanning.

---

## 2. Problem Statement

### Problem Being Solved
Home networks have grown to 30–100+ connected devices spanning smartphones, laptops, smart TVs, IoT sensors, home automation gear, gaming consoles, and network infrastructure. No single tool ties together firewall data (pfSense), wireless mesh data (TP-Link Deco), and DNS-level intelligence (AdGuard Home) into a cohesive, always-on, self-hosted platform with real-time push alerts.

Specific gaps in existing tooling:
- Router admin panels show minimal device info with no history or enrichment.
- TP-Link Deco has no official API; the app shows clients but offers no integration or automation.
- Fing provides excellent identification but requires cloud accounts, paywalled features, and has no firewall, mesh, or DNS integration.
- pfSense has deep visibility but presents data across disconnected screens with no unified device-centric view.
- AdGuard Home tracks DNS per client but does not correlate with device identity or firewall behaviour.
- Manual tools (nmap, arp-scan) give point-in-time snapshots with no continuous monitoring or alerting.
- No tool identifies newly joined devices with product-level accuracy (make, model, OS) automatically.
- No tool provides real-time availability monitoring of specific devices with sub-minute alerting.
- No tool tracks internet speed over time alongside network device data in a unified view.
- Device lifecycle management (archiving retired devices, permanent deletion) is not supported by any self-hosted tool.

### Target Users
**Primary:** Technically proficient home network operators running pfSense as their firewall/router, TP-Link Deco mesh for wireless coverage, and AdGuard Home for DNS-level ad-blocking. Comfortable with Docker, SSH, and command-line tools. Value data ownership and privacy over convenience. Want deep network visibility without third-party cloud services.

**Secondary:** Household members who benefit from a clean, readable dashboard showing device status without needing to understand the underlying technology. May be assigned as "owner" of specific devices.

### Context
NetSentry is inspired by Fing but goes further: it runs entirely locally, integrates with the user's existing infrastructure (pfSense, Deco, AdGuard), and pushes native phone alerts via ntfy or Telegram without any cloud relay for device data. It is designed to be deployed once and run continuously with minimal maintenance overhead. The project has a known FW_agent integration candidate (existing pfSense agentic diagnostic tool) for Phase 5.

---

## 3. Feature Inventory

| Feature | Description | Status | Priority | Location |
|---------|-------------|--------|----------|----------|
| Local Network Scanning | Active ARP, ICMP, TCP, OS fingerprinting, mDNS/SSDP | Not Started | Must-have | scanner/ |
| Device Identification & Classification | Multi-source fingerprinting + optional AI enrichment for product type and OS | Not Started | Must-have | identification/ |
| Device Categorisation & Ownership | User-defined category, subcategory, and owner assignment per device | Not Started | Must-have | db/device/ |
| Device Inventory, History & Lifecycle | Persistent enriched database; archive (historic/hidden) and permanent delete | Not Started | Must-have | db/ |
| Real-Time Availability Monitoring | Per-device high-frequency ping/probe with alerting on state change | Not Started | Must-have | monitor/ |
| Internet Speed Monitor | Scheduled speed tests with historical stats and trend reporting | Not Started | Must-have | speedtest/ |
| Push Notifications (ntfy + Telegram) | Real-time alerts via ntfy and/or Telegram Bot for network events | Not Started | Must-have | notifications/ |
| TP-Link Deco Integration | Mesh topology, per-client Wi-Fi data, AP assignment | Not Started | Must-have | integrations/deco/ |
| pfSense Integration | DHCP, ARP, firewall states, traffic, VLAN | Not Started | Must-have | integrations/pfsense/ |
| AdGuard Home Integration | DNS query profiles, block stats, client heuristics | Not Started | Should-have | integrations/adguard/ |
| Web Dashboard | React SPA: device table, detail, mesh map, availability, speed stats | Not Started | Must-have | frontend/ |
| REST API | FastAPI server exposing device, event, scan, speed, monitor data | Not Started | Must-have | api/ |
| Event & Alert Engine | Event detection, classification, notification routing | Not Started | Must-have | events/ |
| Network Map | Visual topology: VLANs + Deco mesh overlay | Not Started | Should-have | frontend/map/ |
| Historical Analytics | Uptime trends, traffic patterns, DNS evolution, speed history | Not Started | Should-have | analytics/ |
| FW_agent Integration | Bridge to existing pfSense agentic diagnostic tool | Not Started | Nice-to-have | integrations/fwagent/ |

### Feature Details

---

#### Local Network Scanning

**User Story:** As a network operator, I want NetSentry to actively and continuously scan my local network so that every device is discovered and kept current without manual intervention.

**Acceptance Criteria:**
- [ ] ARP sweep discovers all devices on configured subnets on a 5-minute default schedule (configurable)
- [ ] ICMP ping sweep supplements ARP for cross-VLAN visibility
- [ ] TCP SYN probe on common ports (22, 80, 443, 8080, 8443, 554, 1883) runs every 15 minutes
- [ ] Full port scan (65535 ports) on known devices runs daily
- [ ] OS fingerprinting (nmap -O) runs on new device discovery and weekly refresh
- [ ] Service detection (nmap -sV) runs on port change and weekly
- [ ] mDNS/Bonjour and SSDP/UPnP multicast listeners run continuously (passive)
- [ ] NetBIOS (nbtscan) queries run every 15 minutes
- [ ] Scan profiles supported: Quick (ARP + ICMP), Standard (+ common ports), Deep (+ OS fingerprint)
- [ ] On-demand scan trigger available via API and dashboard button
- [ ] Scan rate limiting is configurable (packets per second)
- [ ] Subnet list is configurable or auto-detected from host interfaces
- [ ] MAC vendor resolved from bundled IEEE OUI (Wireshark manuf) with weekly auto-update
- [ ] Hostname resolved from mDNS, NetBIOS, DHCP hostname, and DNS PTR — all sources tracked
- [ ] /24 ARP sweep completes in under 30 seconds; standard scan under 60 seconds

**Dependencies:** Docker host networking or macvlan for Layer 2 ARP access; nmap, arp-scan, scapy, fping installed in container
**Status:** Not Started
**Confidence:** [HIGH]

---

#### Device Identification & Classification

**User Story:** As a network operator, I want NetSentry to automatically identify what each device is — its product type, make/model, and operating system — using every available signal so that I understand my network without manually looking up MAC addresses.

**Acceptance Criteria:**
- [ ] Identification pipeline runs automatically on every newly discovered device and on a weekly refresh for existing low-confidence devices
- [ ] **MAC OUI lookup:** Manufacturer derived from IEEE OUI database; contributes to product type and OS inference
- [ ] **Open port fingerprinting:** Common port patterns mapped to device types (e.g., port 9100 → printer; 1883 → MQTT broker/IoT hub; 554 → camera/NVR; 5353 → Apple device; 9090 → server/monitoring)
- [ ] **OS fingerprinting:** nmap -O result (OS family and version) stored and displayed per device
- [ ] **mDNS/Bonjour service type:** Service type strings (e.g., `_airplay._tcp`, `_ipp._tcp`, `_smb._tcp`) mapped to device category and OS family
- [ ] **SSDP/UPnP device type:** `deviceType` field from UPnP description XML used to classify device
- [ ] **DNS query patterns:** AdGuard query logs analysed for vendor-specific domain patterns (e.g., `*.apple.com`, `*.amazon.com`, `*.samsung.com`) to infer manufacturer
- [ ] **Deco-reported device type:** Device type field from Deco client list used as a classification signal
- [ ] **Heuristic scoring:** All signals combined into a weighted confidence score; highest-confidence classification selected and stored
- [ ] **AI enrichment (optional):** When `ENABLE_AI_IDENTIFICATION=true`, devices with confidence below threshold are submitted to Claude API with all available signals; structured JSON response requested containing: `product_type`, `os_family`, `os_version`, `manufacturer`, `model_guess`, `confidence`, `reasoning`
- [ ] AI enrichment result stored with source attribution (`source: ai`) and confidence score
- [ ] AI enrichment rate-limited: max 10 API calls per scan cycle; only triggered when identification confidence < configurable threshold (default: 0.6)
- [ ] Identification result (all contributing signals + confidence breakdown) displayed on device detail page
- [ ] User can manually override any AI or heuristic classification; manual overrides (`source: manual`) are never overwritten by automatic processes
- [ ] OS family stored independently of product type (e.g., device type "Smart TV" with OS "Tizen 6.0")

**Dependencies:** Scanner Engine; AdGuard integration (DNS signal); Deco integration (Deco type signal); optional Anthropic API key
**Status:** Not Started
**Confidence:** [HIGH]

---

#### Device Categorisation & Ownership

**User Story:** As a network operator, I want to assign each device a category, subcategory, and an owner so that I can organise and filter my device inventory in a way that reflects how my household uses the network.

**Acceptance Criteria:**
- [ ] Each device has a `category` field drawn from a predefined controlled vocabulary (see below)
- [ ] Each device has an optional `subcategory` field for finer classification within a category
- [ ] Each device has an optional `owner` field (free text, e.g., "Ian", "Shared", "Infrastructure")
- [ ] Each device has an optional `friendly_name` field (overrides hostname in all UI displays)
- [ ] Each device has an optional `notes` field (free text, markdown supported)
- [ ] Category, subcategory, owner, friendly name, and notes are all editable from the device detail page and inline in the device table
- [ ] Device table supports filtering by category, subcategory, and owner
- [ ] Device table supports grouping by category or owner
- [ ] Auto-classification from the Identification pipeline pre-populates `category` on first discovery; user can accept or override
- [ ] **Predefined categories:** Personal Device, Server, Network Infrastructure, Smart Home, Entertainment, Printer, Camera / Security, IoT Sensor, Unknown, Other
- [ ] **Predefined subcategories:**
  - Personal Device → Phone, Tablet, Laptop, Desktop, Wearable
  - Server → Home Server, NAS, Virtual Machine, Container Host, Raspberry Pi
  - Network Infrastructure → Router/Firewall, Switch, Access Point, Mesh Node, Modem, VPN Appliance
  - Smart Home → Smart Speaker, Smart Display, Smart Bulb, Smart Plug, Smart Lock, Thermostat, Hub/Controller
  - Entertainment → Smart TV, Streaming Stick, Games Console, Media Player, Projector
  - Printer → Inkjet Printer, Laser Printer, Label Printer, 3D Printer, Scanner
  - Camera / Security → IP Camera, NVR/DVR, Doorbell, Alarm Panel
  - IoT Sensor → Temperature Sensor, Motion Sensor, Energy Monitor, Weather Station
- [ ] User can add custom subcategories; persisted in `CustomSubcategory` table
- [ ] All category/owner fields exposed via REST API for filtering and grouping

**Dependencies:** Device Inventory; Identification pipeline (for auto-population)
**Status:** Not Started
**Confidence:** [HIGH]

---

#### Device Inventory, History & Lifecycle

**User Story:** As a network operator, I want a persistent record of every device ever seen on my network with the ability to archive retired devices or permanently delete them, so that my active device view stays clean without losing historical context.

**Acceptance Criteria:**
- [ ] Every device stored with MAC as primary key (immutable)
- [ ] All historical IP assignments tracked with first_seen, last_seen, and source
- [ ] All resolved hostnames stored with source attribution
- [ ] Vendor, device type, OS family, open ports, category, subcategory, owner, friendly name, and notes all stored and versioned
- [ ] Deco node assignment, Wi-Fi band, and connection type tracked per device
- [ ] First seen, last seen, and online/offline status maintained
- [ ] Tag system: arbitrary tags per device (many-to-many)
- [ ] All changes generate Events stored in the database
- [ ] Device detail page shows full enriched view from all data sources
- [ ] **Lifecycle states:** `active` (default), `historic` (archived/hidden), `deleted` (pending purge)
- [ ] **Archive:** User can set any device to Historic; it is hidden from the default active device list but fully retained in the database
- [ ] Historic devices are accessible via a "Show historic" toggle in the device table (off by default); displayed with a muted style and "Historic" badge
- [ ] Historic devices do NOT trigger new-device or device-offline alerts if they reappear; they are silently re-activated to Active with an informational event logged
- [ ] **Permanent delete:** User can permanently and irreversibly delete a device and all associated records via a confirmation dialog (must type the device name or MAC to confirm)
- [ ] Permanently deleted devices are purged from all tables; a `DeletionAuditLog` entry (MAC, deleted_at) is retained permanently
- [ ] If a permanently deleted device's MAC reappears on the network, it is treated as a brand-new device
- [ ] Bulk archive and bulk delete operations supported (multi-select in device table)

**Dependencies:** Scanner Engine (Phase 1); all integration modules
**Status:** Not Started
**Confidence:** [HIGH]

---

#### Real-Time Availability Monitoring

**User Story:** As a network operator, I want to designate specific critical devices for real-time availability monitoring so that I am alerted within seconds if one goes offline, independently of the main scan cycle.

**Acceptance Criteria:**
- [ ] Any active device in the inventory can be individually opted into availability monitoring via a toggle on the device detail page
- [ ] Monitored devices are probed at a configurable interval per device (default: 30 seconds; minimum: 10 seconds)
- [ ] Probe method configurable per device: ICMP ping (default), TCP port check (specify port), or HTTP/HTTPS health check (specify URL path)
- [ ] A device is considered "down" after a configurable number of consecutive probe failures (default: 2)
- [ ] An alert fires immediately on up → down and down → up transitions
- [ ] Alert payload includes: friendly name, IP, MAC, category, owner, time of transition, outage duration (on recovery)
- [ ] Availability monitoring runs as an independent APScheduler task; does not wait for the main scan cycle
- [ ] Availability state (up / down / unknown) displayed prominently on the device detail page and in the device table for all monitored devices
- [ ] Uptime percentage calculated and displayed for last 24h, 7d, and 30d per monitored device
- [ ] Availability history stored: each up/down transition with timestamp and duration
- [ ] Dashboard has a dedicated "Monitored Devices" panel showing current status of all monitored devices at a glance
- [ ] Availability alerts dispatched to all enabled notification channels and respect quiet hours settings
- [ ] Maximum 50 concurrently monitored devices (configurable via `AVAILABILITY_MAX_MONITORED`)

**Dependencies:** Device Inventory; Event & Alert Engine; Notification Engine
**Status:** Not Started
**Confidence:** [HIGH]

---

#### Internet Speed Monitor

**User Story:** As a network operator, I want NetSentry to run internet speed tests at scheduled intervals and show historical speed trends so I can track whether my ISP is delivering contracted speeds and correlate drops with network events.

**Acceptance Criteria:**
- [ ] Speed tests run automatically on a configurable schedule (default: every 6 hours)
- [ ] Speed test can be triggered on-demand from the dashboard
- [ ] Speed test backend is configurable: Ookla (speedtest-cli), LibreSpeed (librespeed-cli, self-hosted), or fast.com
- [ ] Results captured per test: download (Mbps), upload (Mbps), latency/ping (ms), jitter (ms), packet loss (%), server name/location, timestamp, backend used
- [ ] Results stored in `SpeedTestResult` table with full history
- [ ] Dashboard Speed panel shows: latest download/upload/latency values, trend sparklines for last 24h and 7d
- [ ] Full speed history page: time-series chart with selectable range (24h, 7d, 30d, all time), download/upload/latency overlaid
- [ ] Statistics displayed: average, min, max, 95th percentile over selected range
- [ ] Alert triggered if download or upload falls below a configurable threshold on two consecutive tests
- [ ] Alert triggered if latency exceeds a configurable threshold
- [ ] Speed results visualised alongside the event timeline (speed drop events annotated on the timeline)
- [ ] Speed test is skipped (non-alerting) if the test server is unreachable; failure is logged
- [ ] When LibreSpeed selected, the LibreSpeed server container is included in Docker Compose stack

**Dependencies:** Internet connectivity; Notification Engine
**Status:** Not Started
**Confidence:** [HIGH]

---

#### Push Notifications (ntfy + Telegram)

**User Story:** As a network operator, I want to receive real-time push notifications on my phone via ntfy or Telegram when network events occur so I am immediately aware of new devices, availability failures, and speed drops without checking the dashboard.

**Acceptance Criteria:**
- [ ] **ntfy channel:** ntfy included in Docker Compose stack (self-hosted); ntfy.sh upstream relay configurable for iOS delivery
- [ ] ntfy notifications delivered within 5 seconds (Android), 15 seconds (iOS with upstream relay)
- [ ] **Telegram channel:** Telegram Bot API integration; operator configures Bot token and Chat ID via Docker secret and env var
- [ ] Telegram messages sent via `sendMessage` API with Markdown formatting (bold names, `code` for IPs/MACs)
- [ ] Telegram messages include a deep-link URL to the relevant device/event in the dashboard
- [ ] Both ntfy and Telegram can be active simultaneously; alerts dispatched to all enabled channels
- [ ] **Apprise** available as tertiary multi-channel option (email, Discord, Slack, webhooks, 80+ services)
- [ ] Alert types: new device joined, unknown device online, monitored device down, monitored device recovered, Deco node offline, pfSense/WAN down, speed below threshold, scan complete summary
- [ ] Notification priority levels: urgent (unknown device, monitored device down), high (known event), default (informational)
- [ ] Quiet hours: suppress non-critical notifications during configured hours; urgent alerts bypass quiet hours
- [ ] Per-alert-type channel routing configurable (e.g., Telegram for urgent, ntfy for informational)
- [ ] Notification rate limiting: configurable aggregation window per device and alert type
- [ ] Grace period for transient new-device alerts (configurable, default: 2 missed cycles)
- [ ] Test notification button in settings UI per configured channel
- [ ] Channel configuration validated at startup; failures logged as warnings; system continues operating

**Dependencies:** Phase 1 Scanner + Event Engine; Telegram Bot token + Chat ID; optional ntfy token
**Status:** Not Started
**Confidence:** [HIGH]

---

#### TP-Link Deco Mesh Integration

**User Story:** As a network operator, I want NetSentry to show me which Deco node each device connects through, what Wi-Fi band it uses, and real-time per-device speeds so I can understand wireless layer behaviour.

**Acceptance Criteria:**
- [ ] NetSentry authenticates against the Deco main node's local web admin interface using owner credentials
- [ ] Encrypted JSON payload correctly decrypted and parsed (mirroring ha-tplink-deco approach)
- [ ] Session maintained with automatic re-authentication on 403 errors
- [ ] Client list polled every 30 seconds (configurable, minimum 10 seconds)
- [ ] Each device record includes: MAC, IP, hostname, online status, device type, connection type (wired/wireless)
- [ ] Real-time upload/download speed (bytes/sec) captured per connected device
- [ ] Each device mapped to its connected Deco node (by Deco MAC/name)
- [ ] Wi-Fi band (2.4 GHz / 5 GHz) recorded per device
- [ ] All Deco nodes listed with role (main/satellite), online status, and performance metrics
- [ ] Deco data cross-referenced with pfSense DHCP to resolve IP when Deco reports "UNKNOWN" (AP mode)
- [ ] Mesh topology map shown in dashboard: Deco nodes and their connected clients
- [ ] Alert triggered if a Deco satellite node goes offline
- [ ] Roaming events (device moves between Deco nodes) detected and stored as events
- [ ] System degrades gracefully if Deco unreachable; scanner-only data continues

**Dependencies:** Deco in Access Point mode; owner credentials; Phase 1 device inventory
**Status:** Not Started
**Confidence:** [HIGH]

---

#### pfSense Integration

**User Story:** As a network operator, I want NetSentry to pull data from my pfSense firewall so I can see per-device traffic, firewall rule assignments, DHCP leases, and VLAN membership in a single view.

**Acceptance Criteria:**
- [ ] pfSense REST API client (pfrest.org) authenticates and handles errors gracefully
- [ ] DHCP leases synchronised: hostname, lease start/end, static vs dynamic
- [ ] ARP table polled and correlated with device inventory
- [ ] Per-device active connection count and bytes in/out from firewall state table
- [ ] Firewall rules cross-referenced to identify rules referencing each device
- [ ] VLAN and interface assignment visible per device
- [ ] pfSense gateway status (WAN health, latency) shown in dashboard
- [ ] pfSense system info (uptime, CPU, memory, version) shown
- [ ] Alert triggered if pfSense becomes unreachable
- [ ] Alert triggered if WAN gateway goes down
- [ ] SSH fallback to `pfsense_proxy.py` pattern when REST API unavailable
- [ ] pfSense data latency no more than 30 seconds behind live state

**Dependencies:** pfSense REST API package installed on firewall; Phase 1 device inventory
**Status:** Not Started
**Confidence:** [HIGH]

---

#### AdGuard Home Integration

**User Story:** As a network operator, I want to see per-device DNS profiles so I understand what domains each device queries and how many are blocked.

**Acceptance Criteria:**
- [ ] AdGuard Home REST API client authenticates with Basic Auth
- [ ] Per-device DNS query log polled with timestamps, query types, and responses
- [ ] Aggregated stats retrieved: query counts, top blocked domains, top clients
- [ ] Per-device DNS profile stored: top queried domains, blocked count, query volume over time
- [ ] DNS query patterns fed as a signal into the Device Identification pipeline
- [ ] Ad-block effectiveness per device displayed: percentage blocked, blocklists triggered
- [ ] Suspicious query detection: flag devices with excessive volume or known-bad domain queries
- [ ] AdGuard status panel in dashboard: filter status, upstream DNS, DNSSEC
- [ ] Integration degrades gracefully if AdGuard unreachable

**Dependencies:** AdGuard Home reachable on LAN; Phase 1–3 complete for full enrichment pipeline
**Status:** Not Started
**Confidence:** [HIGH]

---

#### Web Dashboard

**User Story:** As a network operator, I want a web-based dashboard accessible from any LAN device so I can see all devices, availability status, internet speed, and recent events at a glance.

**Acceptance Criteria:**
- [ ] Dashboard accessible from any browser on the LAN
- [ ] Device table: friendly name, IP, MAC, vendor, category, subcategory, owner, OS, online status, last seen, Deco node, Wi-Fi band, availability monitor status badge
- [ ] Device table: filter by category, subcategory, owner, online status; "Show historic" toggle (off by default); historic devices shown with muted style and badge
- [ ] Device table: group by category or owner; bulk select for bulk archive/delete
- [ ] Device detail page: all identification signals and confidence breakdown; category/owner/notes (inline editable); availability uptime stats and history; historical IPs; open ports; DNS profile; pfSense traffic; Deco assignment; AI identification result with reasoning
- [ ] Scan controls: trigger on-demand scan, select profile, view last scan time
- [ ] Events timeline: filterable by type, severity, device; speed drop events annotated inline
- [ ] **Monitored Devices panel:** current up/down status, uptime % (24h/7d/30d) for all monitored devices
- [ ] **Internet Speed panel:** latest download/upload/latency; sparklines for last 24h and 7d; link to full speed history page
- [ ] Speed history page: full time-series chart, selectable range, avg/min/max/p95 stats
- [ ] Mesh topology view: Deco nodes, connected clients, health
- [ ] Network map: VLAN topology + Deco mesh overlay
- [ ] pfSense status panel; AdGuard status panel
- [ ] Settings page: integration credentials; scan schedules; notification channel config (ntfy, Telegram, Apprise); speed test backend and schedule; AI enrichment toggle and API key; data retention settings
- [ ] Responsive layout for mobile browser use
- [ ] Optional HTTPS via user-provided or auto-generated self-signed cert

**Dependencies:** REST API; all integration modules
**Status:** Not Started
**Confidence:** [HIGH]

---

## 4. Functional Requirements

### Core Behaviours
- The system operates on a continuous **scan → identify → enrich → store → alert** loop running autonomously once deployed.
- Scanner Engine performs ARP sweeps, ICMP probes, and TCP SYN probes on APScheduler-managed schedules.
- Discovered devices are matched against the full inventory (including Historic devices) or created as new entries.
- The Identification Pipeline runs on every new device and periodically on existing low-confidence devices; it consults all available signals and optionally the Claude API.
- The Deco, pfSense, and AdGuard pollers each run independently on their own schedules.
- The Enrichment Engine merges all data source outputs into a unified device record after each cycle.
- The Availability Monitor runs on its own independent schedule, probing only opted-in devices at high frequency.
- The Speed Monitor runs scheduled tests independently of device scanning.
- Changes (new device, IP change, offline, new port, new Deco node, availability state change, speed threshold breach) generate Events.
- Events are immediately evaluated by the Alert Engine and dispatched to configured channels (ntfy, Telegram, Apprise).
- The REST API provides current state; the React SPA polls the API for updates.
- Historic devices are excluded from the default device list and from new-device/offline alerts.

### Input/Output Specifications
- **Inputs:** Network traffic (ARP/ICMP/TCP), pfSense REST API, Deco local API (encrypted JSON), AdGuard REST API, Claude API (optional), speedtest CLI output, user configuration (YAML/env vars).
- **Outputs:** SQLite device inventory, event log, speed test history, availability history, REST API, ntfy notifications, Telegram messages, web dashboard, audit log.
- **Key REST endpoints:** `GET /devices`, `GET /devices/{mac}`, `PATCH /devices/{mac}`, `DELETE /devices/{mac}`, `GET /events`, `POST /scan/trigger`, `GET /availability`, `GET /availability/{mac}`, `POST /availability/{mac}/enable`, `GET /speedtest/results`, `POST /speedtest/trigger`, `GET /system/health`, `GET /deco/topology`, `GET /notifications/test/{channel}`.

### Business Logic Rules
- MAC address is the canonical device identifier; IP addresses are mutable.
- A device is "online" if seen in the most recent scan cycle; "offline" after two consecutive missed cycles (configurable).
- **Historic devices** that reappear are silently re-activated to Active with an informational event; they do not trigger new-device alerts.
- **Permanently deleted** device MACs that reappear are treated as brand-new devices.
- AI identification is only triggered when confidence < threshold AND the device has no manual override.
- Manual overrides (`source: manual`) are never overwritten by automatic processes.
- Speed test baseline = median of last 10 results; threshold alerts compare against this rolling baseline.
- Notification rate limiting applies per-device and per-alert-type to prevent alert storms.
- Deco auto-re-authenticates on 403; pfSense REST falls back to SSH automatically when unreachable.

---

## 5. Non-Functional Requirements

### Performance
- /24 ARP sweep: under 30 seconds. Standard scan: under 60 seconds.
- Availability Monitor: probe interval as low as 10 seconds; alert latency ≤15 seconds from first failure to notification.
- Deco and pfSense data freshness: within 30 seconds of polling.
- ntfy latency: ≤5 seconds (Android), ≤15 seconds (iOS). Telegram: ≤5 seconds from event to send.
- REST API: <200ms for device list (up to 200 devices).
- Speed test runs in a separate process; does not block scanner or availability monitor.
- Docker stack RAM: <512 MB at idle; <768 MB during active scanning.

### Security
- All credentials (pfSense, Deco, AdGuard, Telegram Bot token, Anthropic API key) stored as Docker secrets; never in the database.
- Web UI and REST API are LAN-only by default.
- Optional HTTPS via user-provided or auto-generated self-signed cert.
- Container runs as non-root where possible; `CAP_NET_RAW` scoped to scanner only.
- All config changes and manual actions in audit log with timestamps.
- AI enrichment: only non-PII signals submitted (MAC vendor, ports, mDNS type, OS family, hostname pattern, DNS domain patterns — no raw IPs, no user-assigned names). Disabled by default; explicit opt-in required.
- Telegram notifications contain device friendly names and event type only; no raw network topology data.
- Permanent device deletion enforces a confirmation dialog requiring the user to type the device name or MAC.

### Scalability
- Target: 10–200 active devices. Parallel scanning with configurable rate limiting.
- Availability Monitor: up to 50 concurrent monitored devices (configurable).
- SQLite sufficient for all tables at home network scale; Redis optional beyond 150 devices.

### Availability
- All integrations degrade gracefully; core scanning and availability monitoring continue if any external target is unreachable.
- No single integration failure causes a system crash. Data persists across container restarts.

---

## 6. AI/ML Specifications

### Models and Providers
- **Provider:** Anthropic Claude API (claude-haiku by default for cost efficiency; configurable via `AI_IDENTIFICATION_MODEL`)
- **Purpose:** Device identification enrichment for newly discovered or low-confidence devices
- **Default state:** Disabled (`ENABLE_AI_IDENTIFICATION=false`); requires explicit opt-in and API key

### Prompt Patterns
For each candidate device, the Identification Engine submits a structured prompt containing: MAC OUI vendor string, open ports and detected services, mDNS service types, UPnP device type string, nmap OS fingerprint, sanitised hostname pattern, DNS domain patterns from AdGuard. The model is instructed to return a JSON object only:

```json
{
  "product_type": "Smart TV",
  "os_family": "Tizen",
  "os_version": "6.0",
  "manufacturer": "Samsung",
  "model_guess": "Samsung Smart TV (2021)",
  "confidence": 0.82,
  "reasoning": "MAC OUI is Samsung, mDNS advertises _samsungtv._tcp, DNS queries to *.samsung.com"
}
```

### Context Management
- Each AI call is stateless (single-turn); no conversation history maintained.
- Results cached per device by signal fingerprint hash; identical signal sets do not trigger a re-call.
- API errors are logged and non-fatal; device identification falls back to heuristic result.

---

## 7. Data Architecture

### Data Models

| Entity | Primary Key | Key Relationships |
|--------|-------------|-------------------|
| Device | mac_address (TEXT) | Has many: IpAssignment, Event, DnsProfile, PortScan, MeshAssignment, Tag, AvailabilityEvent, IdentificationResult |
| IpAssignment | id (INTEGER) | Belongs to Device. IP, first_seen, last_seen, source |
| MeshAssignment | id (INTEGER) | Belongs to Device. Deco node MAC, band, speed, connected_at, disconnected_at |
| DecoNode | mac_address (TEXT) | Name, role (main/satellite), model, online status, CPU, memory |
| Event | id (INTEGER) | Belongs to Device (nullable). Type, severity, timestamp, details JSON, notification_sent |
| DnsProfile | id (INTEGER) | Belongs to Device. Hourly aggregates: query_count, blocked_count, top_domains JSON |
| PortScan | id (INTEGER) | Belongs to Device. Port, protocol, service, version, first_seen, last_seen |
| TrafficSample | id (INTEGER) | Belongs to Device. bytes_in, bytes_out, connections, timestamp |
| Tag | id (INTEGER) | Many-to-many with Device via DeviceTag junction |
| Notification | id (INTEGER) | Linked to Event. Channel (ntfy/telegram/apprise), status, priority, sent_at |
| ScanRun | id (INTEGER) | type, start, end, devices_found, errors |
| IdentificationResult | id (INTEGER) | Belongs to Device. source (heuristic/ai/manual), product_type, os_family, os_version, manufacturer, model_guess, confidence, reasoning, created_at |
| AvailabilityMonitor | mac_address (TEXT) | Config: enabled, interval_seconds, probe_method, probe_port, consecutive_failures_threshold |
| AvailabilityEvent | id (INTEGER) | Belongs to Device. state (up/down), timestamp, duration_seconds |
| SpeedTestResult | id (INTEGER) | Standalone. download_mbps, upload_mbps, ping_ms, jitter_ms, packet_loss_pct, server_name, backend, tested_at |
| CustomSubcategory | id (INTEGER) | User-defined subcategory labels |
| DeletionAuditLog | id (INTEGER) | mac_address (TEXT, retained permanently), deleted_at |
| SystemConfig | key (TEXT) | Key-value store for runtime settings |

### Relationships and Constraints
- `Device.lifecycle` enum: `active` | `historic` | `deleted` (soft-delete pending purge).
- `IdentificationResult` with `source: manual` is never overwritten by automatic processes.
- `AvailabilityMonitor` config cascades delete when a device is deleted.
- `AvailabilityEvent` records pruned after 90 days (configurable). `SpeedTestResult` pruned after 365 days (configurable). `DnsProfile` and `TrafficSample` pruned after 30 days (configurable). `Event` and `DeletionAuditLog` retained permanently.

### Storage Mechanisms
- **Primary:** SQLite via `aiosqlite` for async FastAPI compatibility.
- **Optional cache:** Redis for hot data (current states, latest speed result) when device count exceeds 150.
- **File storage:** OUI database; AI identification result cache (keyed by signal fingerprint hash).
- **Secrets:** Docker secrets; never stored in SQLite or plain-text environment variables.

---

## 8. Integration Map

### External Services

| Service | Access Method | Data / Action | Auth |
|---------|--------------|---------------|------|
| pfSense | REST API (pfrest.org, HTTPS) + SSH fallback | DHCP, ARP, firewall states/rules, interface, gateway, system info | API key (Bearer) |
| TP-Link Deco | Local web admin API (encrypted JSON) | Client list, per-client speed, AP node, Wi-Fi band, mesh topology | Owner credentials |
| AdGuard Home | REST API (/control/*) | Query log, stats, client list, filter status, DNS config | Basic Auth |
| ntfy | HTTP PUT/POST | Push notification delivery | Bearer token (optional) |
| Telegram Bot API | HTTPS POST to api.telegram.org | Notification delivery with Markdown + deep-link | Bot token + Chat ID |
| Anthropic Claude API | HTTPS POST to api.anthropic.com/v1/messages | Device identification enrichment | API key (Bearer) |
| Speedtest.net (Ookla) | speedtest-cli subprocess | Download, upload, ping, jitter, packet loss | None / account token |
| LibreSpeed | librespeed-cli → local LibreSpeed container | Download, upload, ping, jitter | None |
| IEEE OUI database | HTTP GET (Wireshark manuf URL) | MAC vendor mappings | None |

### Authentication Methods
All credentials stored as Docker secrets or env vars; never hardcoded. ntfy: optional Bearer token. Telegram: Bot token (Docker secret) + Chat ID (env var). Claude API key: Docker secret. All others as previously documented.

### Third-Party Dependencies
ha-tplink-deco (Deco API reference), MrMarble/deco (Deco API reference), pfrest.org (pfSense REST package), ntfy (self-hosted push), Apprise (multi-channel notifications), speedtest-cli (Ookla), librespeed-cli + LibreSpeed server (self-hosted speed test), Anthropic Python SDK (optional, AI identification).

---

## 9. Configuration Reference

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `PFSENSE_API_URL` | pfSense REST API base URL | Yes | — |
| `PFSENSE_API_KEY` | pfSense API key (prefer Docker secret) | Yes | — |
| `DECO_HOST` | TP-Link Deco main node IP | Yes | — |
| `DECO_USERNAME` | Deco owner username (prefer Docker secret) | Yes | — |
| `DECO_PASSWORD` | Deco owner password (prefer Docker secret) | Yes | — |
| `ADGUARD_URL` | AdGuard Home base URL | Yes | — |
| `ADGUARD_USERNAME` | AdGuard username (prefer Docker secret) | Yes | — |
| `ADGUARD_PASSWORD` | AdGuard password (prefer Docker secret) | Yes | — |
| `NTFY_URL` | ntfy server URL | Yes | http://ntfy:80 |
| `NTFY_TOPIC` | ntfy topic name | Yes | netsentry |
| `NTFY_TOKEN` | ntfy access token (prefer Docker secret) | No | — |
| `NTFY_UPSTREAM_BASE_URL` | ntfy upstream relay for iOS push | No | — |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot token (prefer Docker secret) | No | — |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | No | — |
| `ANTHROPIC_API_KEY` | Claude API key (prefer Docker secret) | No | — |
| `AI_IDENTIFICATION_MODEL` | Claude model for identification | No | claude-haiku-4-5-20251001 |
| `AI_IDENTIFICATION_CONFIDENCE_THRESHOLD` | Min confidence to skip AI call (0.0–1.0) | No | 0.6 |
| `AI_MAX_CALLS_PER_CYCLE` | Max AI API calls per scan cycle | No | 10 |
| `SPEEDTEST_BACKEND` | `ookla`, `librespeed`, or `fast` | No | ookla |
| `SPEEDTEST_INTERVAL` | Speed test interval in seconds | No | 21600 |
| `SPEEDTEST_DOWNLOAD_THRESHOLD_MBPS` | Alert if download falls below (0 = off) | No | 0 |
| `SPEEDTEST_LATENCY_THRESHOLD_MS` | Alert if latency exceeds (0 = off) | No | 0 |
| `AVAILABILITY_MAX_MONITORED` | Max concurrent monitored devices | No | 50 |
| `SCAN_SUBNETS` | Comma-separated subnets to scan | No | auto-detect |
| `SCAN_INTERVAL_ARP` | ARP sweep interval (seconds) | No | 300 |
| `SCAN_INTERVAL_PORTS` | TCP port scan interval (seconds) | No | 900 |
| `SCAN_RATE_LIMIT` | Max packets per second | No | 1000 |
| `DECO_POLL_INTERVAL` | Deco polling interval (seconds, min 10) | No | 30 |
| `DB_PATH` | SQLite database file path | No | /data/netsentry.db |
| `LOG_LEVEL` | DEBUG / INFO / WARNING | No | INFO |
| `TLS_CERT_PATH` | TLS certificate path (optional HTTPS) | No | — |
| `TLS_KEY_PATH` | TLS private key path (optional HTTPS) | No | — |

### Feature Flags
- `ENABLE_DECO_INTEGRATION` (default: true)
- `ENABLE_PFSENSE_INTEGRATION` (default: true)
- `ENABLE_ADGUARD_INTEGRATION` (default: true)
- `ENABLE_AI_IDENTIFICATION` (default: **false** — requires `ANTHROPIC_API_KEY`)
- `ENABLE_TELEGRAM` (default: false — requires `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`)
- `ENABLE_SPEEDTEST` (default: true)
- `ENABLE_LIBRESPEED` (default: false — adds LibreSpeed server to Docker Compose)
- `ENABLE_FULL_PORT_SCAN` (default: true)
- `ENABLE_OS_FINGERPRINTING` (default: true)
- `ENABLE_SNMP` (default: false)
- `ENABLE_REDIS_CACHE` (default: false)

---

## 10. Quality Assessment

### Tested Functionality
_(To be populated as phases are implemented and tested.)_

### Untested Areas
_(All areas untested at project start — greenfield build.)_

### Technical Debt
- Deco API is reverse-engineered and fragile against firmware updates; adapter layer required.
- Host networking for ARP scanning requires `CAP_NET_RAW`; macvlan adds user complexity.
- Deco single-owner-session limitation requires user education (dedicated manager account for the Deco app).
- AI identification calls a paid external API; cost managed via rate limiting and signal fingerprint caching.
- Telegram Bot API requires outbound HTTPS to `api.telegram.org`; users with strict egress rules must whitelist this.
- Ookla speedtest-cli licence restricts automated commercial use; LibreSpeed should be the recommended default for privacy-conscious operators.
- Permanent device deletion is irreversible; confirmation UX must be robust (type-to-confirm pattern).
- No test suite at project start; TDD approach recommended from Phase 1.

---

## 11. Open Questions

- **Q:** Which pfSense REST API version (v1 vs v2) should be targeted as the primary integration?
  **Options:** Target v2 with v1 fallback; target v2 only and document minimum pfSense version.

- **Q:** Should the Deco integration use manager or owner credentials?
  **Context:** Only one owner session allowed simultaneously; owner creds for NetSentry prevent concurrent Deco app use.
  **Options:** Require owner (simpler, sessions clash); investigate manager credential API access coverage.

- **Q:** Should AI identification default to claude-haiku or claude-sonnet?
  **Context:** Device identification is a structured classification task; haiku may be sufficient and significantly cheaper.
  **Options:** Default to haiku; make model configurable via `AI_IDENTIFICATION_MODEL`.

- **Q:** What should the default speed test backend be?
  **Status: RESOLVED** — Default is **LibreSpeed** (self-hosted, privacy-first, no licence concerns). Ookla available as opt-in via `SPEEDTEST_BACKEND=ookla`.

- **Q:** What are the data retention windows for DNS logs, traffic samples, speed results, and availability events?
  **Proposed defaults:** DNS 30d, traffic 30d, speed 365d, availability 90d — all configurable via env var.

- **Q:** Should MAC randomisation detection (iOS/Android per-network MAC rotation) be in scope for v1.0?
  **Context:** Without detection, rotating MACs cause repeated "new device" false positives.

- **Q:** Should the React frontend be served via FastAPI static files or a separate nginx container?
  **Options:** FastAPI static (simpler Compose); nginx (more flexible for HTTPS termination and caching).

- **Q:** Should Telegram notifications include inline keyboard buttons ("View Device", "Mark as Known") requiring a bot polling loop, or plain Markdown messages only for v1.0?
  **Status: RESOLVED** — v1.0 uses **plain Markdown + deep-link URL** (simpler, no bot polling loop). Inline keyboard buttons deferred to a future enhancement.

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-21 | 1.0 | Initial PRD created from NetSentry_PRD_v1.2 source document |
| 2026-03-21 | 1.1 | Added: Device Identification & Classification (multi-source heuristics + optional Claude AI); Device Categorisation & Ownership (controlled vocabulary, owner/friendly name/notes); Device Lifecycle Management (archive/historic hidden state, permanent delete with audit log); Real-Time Availability Monitoring (per-device probe, uptime stats, state-change alerts); Internet Speed Monitor (scheduled tests, trend reporting, threshold alerts); Telegram notification channel; updated data model (IdentificationResult, AvailabilityMonitor, AvailabilityEvent, SpeedTestResult, CustomSubcategory, DeletionAuditLog); updated integration map, config reference, feature flags, and open questions |

---

> **Confidence Markers:** [HIGH] clear from requirements | [MEDIUM] inferred from patterns | [LOW] speculative
>
> **Status Values:** Complete | Partial | Stubbed | Broken | Not Started
