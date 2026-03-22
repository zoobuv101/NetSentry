# EP0003: pfSense & AdGuard Home Integrations

> **Status:** Draft
> **Phase:** 3 — pfSense Integration (parallel-capable with EP0002)
> **Created:** 2026-03-21
> **PRD Reference:** [PRD](../prd.md) · [TRD](../trd.md)

## Summary

Delivers deep firewall visibility via the pfSense REST API (with SSH fallback using the existing `pfsense_proxy.py` pattern) and DNS-level intelligence via the AdGuard Home REST API. After this epic every device record is enriched with DHCP lease data, firewall traffic stats, VLAN membership, and per-device DNS query profiles. The pfSense gateway health and WAN status are also monitored with alerting.

---

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| PRD | Integration | pfSense REST API package (pfrest.org) must be installed on pfSense | Deployment guide must document this prerequisite |
| TRD | Integration | pfSense REST v2 preferred; v1 fallback; SSH fallback on REST failure | Client must handle version detection or explicit config |
| PRD NFR | Performance | pfSense data freshness ≤30s | Poll interval ≤30s |
| PRD | Security | pfSense API key stored as Docker secret | Never in DB or logs |
| TRD | Integration | All integration failures non-fatal | API and dashboard must handle missing pfSense/AdGuard data gracefully |

---

## Business Context

### Problem Statement
pfSense holds the authoritative view of the network — DHCP leases, ARP mappings, per-device traffic, firewall rules, VLAN assignments — but presents this data across disconnected admin screens. AdGuard Home has per-client DNS intelligence but no correlation with device identity. Neither feeds into a unified device view.

**PRD Reference:** PRD §3 — pfSense Integration; AdGuard Home Integration

### Value Proposition
Every device record gains firewall-sourced enrichment (hostname from DHCP, VLAN, traffic stats, firewall rule membership) and DNS-level intelligence (top queried domains, blocked count, suspicious query detection). The DNS query data also feeds the device identification pipeline in EP0005 as a classification signal. WAN health alerts keep the operator informed of connectivity issues.

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| DHCP coverage | 100% of DHCP-assigned devices have hostname from pfSense | Compare DB vs pfSense DHCP lease count |
| pfSense data latency | ≤30s behind live state | Poll timestamp vs current time |
| WAN alert | Alert within 60s of WAN gateway going down | Test by disabling WAN; measure alert receipt time |
| AdGuard DNS profile | Per-device top domains visible in device detail | Manual check for 5 known devices |

---

## Scope

### In Scope
- pfSense REST API client (httpx, Bearer token from Docker secret, v2 with v1 fallback)
- SSH fallback client (paramiko, reusing `pfsense_proxy.py` pattern) triggered when REST API unreachable
- pfSense poller (APScheduler, 30s): DHCP leases, ARP table, firewall states, firewall rules, interface/VLAN data, gateway status, system info
- `traffic_samples` table (Alembic migration); per-device bytes in/out, connection count stored periodically
- pfSense enrichment of device records: hostname (DHCP), VLAN, static vs dynamic lease, firewall rule references
- WAN gateway down alert via Event Engine → Notification Engine
- pfSense unreachable alert
- AdGuard Home REST API client (httpx, Basic Auth from Docker secret)
- AdGuard poller (APScheduler, 60s): query log, stats, client list, filtering status
- `dns_profiles` table (Alembic migration); hourly aggregates per device
- Per-device DNS profile enrichment: top queried domains, blocked count, query volume
- Suspicious query detection: flag devices exceeding query volume threshold or querying known-bad categories
- New API endpoints: `GET /api/v1/pfsense/status`, `GET /api/v1/adguard/status`, `GET /api/v1/devices/{mac}/dns`
- Dashboard panels: pfSense status (gateway health, system info), AdGuard status (filter stats, top blocked domains)
- Device detail page: VLAN, traffic stats, DNS profile, firewall rule references

### Out of Scope
- pfSense firewall rule creation or modification (read-only integration)
- AdGuard blocklist management
- Device identification DNS signal feeding (EP0005 consumes dns_profiles populated here)
- Speed test (EP0008)

### Affected Personas
- **Primary Operator:** Gains firewall-level per-device visibility and DNS intelligence; WAN health alerts

---

## Acceptance Criteria (Epic Level)

- [ ] pfSense REST API client authenticates successfully and polls DHCP, ARP, states, rules, interfaces, gateway, system info every 30 seconds
- [ ] DHCP hostnames from pfSense appear in device records within one poll cycle
- [ ] Per-device traffic stats (bytes in/out, connection count) visible in device detail
- [ ] VLAN assignment displayed per device where applicable
- [ ] SSH fallback activates automatically when pfSense REST API is unreachable; scanner-only data continues otherwise
- [ ] WAN gateway down alert fires within 60 seconds of gateway failure
- [ ] pfSense unreachable alert fires when REST + SSH both fail
- [ ] System continues operating normally if pfSense entirely unreachable
- [ ] AdGuard Home poller authenticates and polls query log and stats every 60 seconds
- [ ] Per-device DNS profile shows top 10 queried domains, blocked count, query volume for each device
- [ ] Suspicious query flag visible on device detail for devices exceeding query threshold
- [ ] `GET /api/v1/pfsense/status` returns gateway health and pfSense system info
- [ ] `GET /api/v1/adguard/status` returns filter stats and top blocked domains
- [ ] System continues operating normally if AdGuard entirely unreachable
- [ ] Deco IP cross-reference: devices showing "UNKNOWN" IP in Deco are resolved via pfSense DHCP lease match

---

## Dependencies

### Blocked By
| Dependency | Type | Status |
|------------|------|--------|
| EP0001 complete | Epic | Must be Done |
| pfSense REST API package installed on pfSense | Operator config | Operator responsibility |
| pfSense API key configured | Operator config | Operator responsibility |
| AdGuard Home reachable on LAN | Operator config | Operator responsibility |

### Blocking
| Item | Impact |
|------|--------|
| EP0005 (Identification) | DNS query patterns are an identification signal; requires dns_profiles populated here |
| EP0009 (Dashboard) | pfSense and AdGuard dashboard panels |

---

## Risks & Assumptions

### Assumptions
- Operator has pfSense REST API package installed (pfrest.org v2); deployment guide covers installation
- AdGuard Home is reachable on LAN at a known IP/port
- `pfsense_proxy.py` SSH pattern (existing from FW_agent project) is reusable as the SSH fallback client

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| pfSense REST API v2 not available on operator's pfSense version | Medium | Medium | Auto-detect API version at startup; fall back to v1; document minimum supported version |
| AdGuard query log pagination performance on high-traffic networks | Medium | Low | Poll only recent entries (last N minutes); store aggregates only, not raw log |
| pfSense firewall states table is large on busy networks | Low | Medium | Only pull per-device summary (aggregate by source IP); not raw state dump |

---

## Technical Considerations

### Architecture Impact
- `netsentry/integrations/pfsense/` package: `client.py` (REST + SSH fallback), `poller.py`, `models.py`
- `netsentry/integrations/adguard/` package: `client.py`, `poller.py`, `models.py`
- Alembic migration 0003: `traffic_samples`, `dns_profiles` tables
- Event Engine extended: WAN gateway down, pfSense unreachable event types

### Integration Points
- pfSense: HTTPS REST to pfSense management IP (port 443); SSH to pfSense management IP (port 22) as fallback
- AdGuard Home: HTTP REST to AdGuard IP (port 3000 default)

---

## Sizing

**Story Points:** 26
**Estimated Story Count:** 6

**Complexity Factors:**
- Two-path pfSense client (REST primary, SSH fallback) with version detection adds complexity
- AdGuard query log aggregation must be efficient to avoid O(n) per-device scans on large logs
- VLAN-aware device enrichment requires careful correlation of interface data with device records

---

## Story Breakdown

- [ ] US0016: pfSense REST API client (authentication, v2/v1 version detection, error handling)
- [ ] US0017: pfSense SSH fallback client (paramiko, pfsense_proxy.py pattern reuse)
- [ ] US0018: pfSense poller (DHCP, ARP, states, rules, interfaces, gateway, system info; device enrichment; traffic_samples table)
- [ ] US0019: pfSense gateway alerting + pfSense status API endpoint + dashboard panel
- [ ] US0020: AdGuard Home client + poller (query log aggregation, dns_profiles table, per-device DNS profile)
- [ ] US0021: AdGuard status API endpoint + dashboard panel + device detail DNS tab

---

## Open Questions

- [ ] Should pfSense REST API version (v1 vs v2) be auto-detected at startup or explicitly configured via env var? Auto-detection preferred but adds startup complexity. — Owner: Implementation decision
- [ ] How should the AdGuard query log be polled efficiently? Recommended: poll only logs from the last 2× poll interval; aggregate into hourly DNS profile buckets. — Owner: Implementation decision

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft from PRD v1.1 + TRD v1.0 |
