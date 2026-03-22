# NetSentry — Story Index

**Project:** NetSentry
**Generated:** 2026-03-21
**Approach:** TDD throughout
**Total:** 45 stories · 193 story points

---

## EP0001 — Foundation (Phase 1) · 8 stories · 34 pts

| ID | Title | Points | Status | File |
|----|-------|--------|--------|------|
| US0001 | Docker Compose Stack Skeleton | 3 | Ready | US0001-docker-compose-stack-skeleton.md |
| US0002 | Python Project Scaffold | 3 | Ready | US0003-US0008-ep0001-remaining.md |
| US0003 | SQLite Schema & Alembic Initial Migration | 4 | Ready | US0003-US0008-ep0001-remaining.md |
| US0004 | Device Repository Layer | 5 | Ready | US0003-US0008-ep0001-remaining.md |
| US0005 | Scanner Engine — ARP, ICMP & NetBIOS | 5 | Ready | US0003-US0008-ep0001-remaining.md |
| US0006 | Scanner Engine — TCP, mDNS/SSDP & OS Fingerprinting | 6 | Ready | US0003-US0008-ep0001-remaining.md |
| US0007 | APScheduler Harness, Scan Profiles & OUI Resolution | 7 | Ready | US0003-US0008-ep0001-remaining.md |
| US0008 | FastAPI Device Endpoints & React Device Table Scaffold | 6 | Ready | US0003-US0008-ep0001-remaining.md |

**Execution order:** US0001 → US0002 → US0003 → US0004 → US0005 → US0006 → US0007 → US0008

---

## EP0002 — Deco + Notifications (Phase 2) · 7 stories · 29 pts

| ID | Title | Points | Status | File |
|----|-------|--------|--------|------|
| US0009 | Deco API Client (Encrypted Protocol, Auth, Session) | 5 | Ready | US0009-US0015-ep0002-deco-notifications.md |
| US0010 | Deco Poller & DB Persistence | 5 | Ready | US0009-US0015-ep0002-deco-notifications.md |
| US0011 | Deco Enrichment & Roaming Detection | 3 | Ready | US0009-US0015-ep0002-deco-notifications.md |
| US0012 | Event Engine — State Change Detection & DB Writes | 4 | Ready | US0009-US0015-ep0002-deco-notifications.md |
| US0013 | Notification Engine — ntfy Channel | 4 | Ready | US0009-US0015-ep0002-deco-notifications.md |
| US0014 | Notification Engine — Telegram Channel | 3 | Ready | US0009-US0015-ep0002-deco-notifications.md |
| US0015 | Notification Config API, Settings UI & Deco Topology Panel | 5 | Ready | US0009-US0015-ep0002-deco-notifications.md |

**Execution order:** US0009 → US0010 → US0011 (parallel with US0012) → US0012 → US0013 → US0014 → US0015

---

## EP0003 — pfSense + AdGuard (Phase 3) · 6 stories · 26 pts

| ID | Title | Points | Status | File |
|----|-------|--------|--------|------|
| US0016 | pfSense REST API Client | 3 | Ready | US0016-US0021-ep0003-pfsense-adguard.md |
| US0017 | pfSense SSH Fallback Client | 3 | Ready | US0016-US0021-ep0003-pfsense-adguard.md |
| US0018 | pfSense Poller — DHCP, ARP, States, Rules & Enrichment | 6 | Ready | US0016-US0021-ep0003-pfsense-adguard.md |
| US0019 | pfSense Gateway Alerting, Status API & Dashboard Panel | 4 | Ready | US0016-US0021-ep0003-pfsense-adguard.md |
| US0020 | AdGuard Home Client, Poller & DNS Profile Storage | 5 | Ready | US0016-US0021-ep0003-pfsense-adguard.md |
| US0021 | AdGuard Status API, Dashboard Panel & Device DNS Tab | 4 | Ready | US0016-US0021-ep0003-pfsense-adguard.md |

**Execution order:** US0016 → US0017 → US0018 → US0019 (parallel with US0020) → US0020 → US0021

---

## EP0004 — Identification, Categorisation & Lifecycle (Phase 4) · 7 stories · 31 pts

| ID | Title | Points | Status | File |
|----|-------|--------|--------|------|
| US0022 | Identification Pipeline Scaffold & Heuristic Engine | 6 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0023 | Heuristic Signal Integration (OS, DNS, Deco) | 4 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0024 | AI Enrichment Module (Claude API, Rate Limiter, Cache) | 6 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0025 | Identification Results DB, Pipeline Scheduler & Override | 3 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0026 | Device Categorisation Model (PATCH, Vocabulary) | 4 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0027 | Device Lifecycle Management (Historic, Delete, Audit Log) | 5 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0028 | Identification UI, Categorisation Inline Edit, Lifecycle UI | 6 | Ready | US0022-US0045-ep0004-ep0007.md |

**Execution order:** US0022 → US0023 → US0024 → US0025 (all chain) · US0026 → US0027 → US0028 (can start after US0025)

---

## EP0005 — Availability Monitoring (Phase 4) · 5 stories · 21 pts

| ID | Title | Points | Status | File |
|----|-------|--------|--------|------|
| US0029 | Availability Monitor Tables & Repository | 3 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0030 | Probe Implementations (ICMP, TCP, HTTP) & State Machine | 4 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0031 | Availability Monitor Manager (Dynamic APScheduler Jobs) | 4 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0032 | Availability Alerting & Notification Integration | 3 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0033 | Availability API Endpoints, Dashboard Panel & Device UI | 4 | Ready | US0022-US0045-ep0004-ep0007.md |

**Execution order:** US0029 → US0030 → US0031 → US0032 → US0033

---

## EP0006 — Internet Speed Monitor (Phase 4) · 4 stories · 18 pts

| ID | Title | Points | Status | File |
|----|-------|--------|--------|------|
| US0034 | Speed Test Tables, Monitor Module & Scheduler | 5 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0035 | Speed Threshold Alerting & Baseline Calculation | 3 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0036 | Speed Test API Endpoints & Dashboard Speed Panel | 4 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0037 | Speed History Page, Timeline Annotation & LibreSpeed Compose | 5 | Ready | US0022-US0045-ep0004-ep0007.md |

**Execution order:** US0034 → US0035 → US0036 → US0037

---

## EP0007 — Full Dashboard, Network Map & Polish (Phase 4) · 8 stories · 34 pts

| ID | Title | Points | Status | File |
|----|-------|--------|--------|------|
| US0038 | Full Device Table (Columns, Sort, Filter, Group) | 5 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0039 | Device Table Bulk Actions (Multi-Select, Archive, Delete) | 4 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0040 | Device Detail Page — Overview, Network & Traffic Tabs | 4 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0041 | Device Detail Page — DNS, Availability & Events Tabs | 4 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0042 | Network Map (Deco Topology + Device Nodes) | 5 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0043 | Events Timeline (Full Filtering, Speed Annotations) | 4 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0044 | Settings Page (All Integration, Notification, Retention Config) | 5 | Ready | US0022-US0045-ep0004-ep0007.md |
| US0045 | Mobile Responsiveness, HTTPS, PWA Manifest & Prod Dockerfile | 5 | Ready | US0022-US0045-ep0004-ep0007.md |

**Execution order:** US0038 → US0039 (parallel) · US0040 → US0041 (parallel) · US0042 · US0043 · US0044 · US0045 (US0045 last)

---

## Alembic Migration Chain

| Migration | Story | Tables Added |
|-----------|-------|-------------|
| 0001_initial | US0003 | devices, ip_assignments, events, scan_runs, system_config, tags, device_tags, notifications, deletion_audit_log |
| 0002_deco | US0010 | mesh_assignments, deco_nodes |
| 0003_pfsense | US0018 | traffic_samples; devices += vlan_id, firewall_rules_json |
| 0004_adguard | US0020 | dns_profiles |
| 0005_identification | US0022 | identification_results |
| 0006_categorisation | US0026 | custom_subcategories; devices += category, subcategory, owner, friendly_name, notes |
| 0007_availability | US0029 | availability_monitors, availability_events |
| 0008_speed | US0034 | speed_test_results |

---

## GitHub Repository Setup (Next Step)

Before coding begins:
1. Create new GitHub repo `netsentry` (public or private)
2. Add `README.md`, `.gitignore` (Python + Node), `LICENSE` (MIT recommended)
3. Configure branch protection on `main`: require PR + CI pass before merge
4. Set up GitHub Actions secrets: `ANTHROPIC_API_KEY` (for CI if AI tests enabled)
5. Start with US0001 — `docker compose up -d` the skeleton

**First command after repo creation:**
```bash
git clone https://github.com/<you>/netsentry.git
cd netsentry
# Start US0001: create docker-compose.yml, Dockerfile
```

---

*Generated by sdlc-studio story — NetSentry PRD v1.1 + TRD v1.0 + Epics EP0001–EP0007*
