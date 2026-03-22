# EP0007: Full Dashboard, Network Map & Polish

> **Status:** Draft
> **Phase:** 4 — AdGuard + Polish
> **Created:** 2026-03-21
> **PRD Reference:** [PRD](../prd.md) · [TRD](../trd.md)

## Summary

Completes the web frontend: the full device table (with category/owner/lifecycle filtering and grouping, inline editing, bulk actions), the comprehensive device detail page (all data sources, identification breakdown, availability stats, DNS profile, pfSense traffic, Deco assignment), the network map (VLAN topology + Deco mesh overlay), the full events timeline (with speed annotations), and the settings page (all integration configs, notification routing, speed test, AI enrichment). This epic polishes NetSentry into a complete, production-ready self-hosted appliance.

---

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| TRD | Frontend | React 18 + TypeScript + Vite + shadcn/ui + Tailwind CSS | All UI components must use this stack |
| TRD ADR-003 | Deployment | FastAPI serves React build via StaticFiles by default; optional nginx override | React build artifact must be copied into correct location in Dockerfile |
| PRD NFR | Responsiveness | Responsive layout suitable for mobile browser use | Tailwind responsive breakpoints required throughout |
| PRD | Security | Optional HTTPS via user-provided cert or auto-generated self-signed | nginx optional overlay; cert path env vars in FastAPI |
| PRD NFR | API performance | `GET /devices` <200ms for 200 devices | Ensure React polling (10s default) does not cause perceptible lag |

---

## Business Context

### Problem Statement
After EP0001–EP0006, all the data is collected and stored but the frontend is a minimal scaffold. The operator needs a polished, complete UI to get value from the full data set — especially the integrated device detail view, the network map, and the settings configuration experience.

**PRD Reference:** PRD §3 — Web Dashboard; all features' UI acceptance criteria

### Value Proposition
NetSentry becomes a complete, production-grade self-hosted network intelligence platform. The operator can manage their entire network — device identification, categorisation, ownership, availability monitoring, speed history, mesh topology, firewall data — from a single responsive web UI accessible from any device on the LAN.

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Dashboard load time | <2s initial load on LAN | Browser DevTools network tab |
| Device table render | <500ms for 200 devices | Measured via React DevTools |
| Mobile usability | All core flows usable on 375px viewport | Manual test on phone browser |
| Settings persistence | All settings survive container restart | Restart container; verify settings unchanged |

---

## Scope

### In Scope
- **Device table (full):** columns (friendly name, IP, MAC, vendor, category, subcategory, owner, OS, online status, last seen, Deco node, Wi-Fi band, availability badge), column show/hide, sort by any column
- Device table filters: category, subcategory, owner, online status, lifecycle (Show historic toggle)
- Device table grouping: by category or by owner
- Device table inline editing: friendly name, category, subcategory, owner (click-to-edit)
- Device table bulk actions: select multiple → bulk archive / bulk delete (confirmation dialog)
- **Device detail page (full):** all data source tabs — Overview (friendly name, category, owner, notes, identification signals + confidence), Network (current IP, all historical IPs, open ports, Deco node, Wi-Fi band, connection type, VLAN), Traffic (pfSense bytes in/out, active connections), DNS (top queried domains, blocked count, blocked %), Availability (monitor toggle, probe config, uptime stats 24h/7d/30d, state history), Events (device-specific event timeline)
- Device detail: edit all metadata fields; identification override; availability monitoring enable/disable
- **Network map:** VLAN topology (Deco nodes positioned by signal strength / manual layout if signal unavailable); device nodes coloured by category; click device → device detail; Deco mesh overlay showing AP-client relationships; react-flow or d3-based interactive map
- **Events timeline (full):** global timeline filterable by event type, severity, device; speed events annotated with download/upload values; pagination or virtual scroll
- **Settings page:** integration credentials (pfSense, Deco, AdGuard, Telegram, ntfy, AI), scan schedule config, notification routing (per-alert-type channel), quiet hours, speed test backend + schedule + thresholds, data retention windows, AI identification toggle + model + threshold
- Optional HTTPS: if `TLS_CERT_PATH` and `TLS_KEY_PATH` set, FastAPI serves HTTPS; self-signed cert auto-generated if paths not set but `HTTPS=true`
- Dashboard API polling interval configurable (default 10s)
- PWA manifest (installable on phone home screen — nice-to-have within this epic)

### Out of Scope
- FW_agent integration UI (Phase 5)
- Voice interface (Phase 5)
- Home Assistant integration (Phase 5)
- Prometheus/Grafana export (Phase 5)
- Wake-on-LAN (Phase 5)

### Affected Personas
- **Primary Operator:** Full management UI; settings configuration; network map
- **Household Members:** Clean categorised device list; owner-filtered view of their own devices

---

## Acceptance Criteria (Epic Level)

- [ ] Device table shows all columns; sort, filter, and group work correctly
- [ ] "Show historic" toggle correctly shows/hides Historic devices
- [ ] Inline editing of friendly_name, category, subcategory, owner persists to DB on blur/enter
- [ ] Bulk archive and bulk delete work for multi-selected devices; confirmation dialogs enforce type-to-confirm for delete
- [ ] Device detail page shows all tabs with correct data from all integrations
- [ ] Identification panel shows all contributing signals, confidence score, and AI reasoning (if available)
- [ ] Availability monitor can be enabled/disabled from device detail; probe method and interval configurable in UI
- [ ] Network map renders Deco nodes and connected devices; click a device node to navigate to device detail
- [ ] Events timeline shows all event types; speed events show download/upload values inline
- [ ] Settings page saves and persists all configuration; container restart retains settings
- [ ] Settings page redacts credentials (shows "configured" / "not configured" status; allows re-entry)
- [ ] All pages render correctly on 375px mobile viewport (iPhone SE)
- [ ] Initial dashboard load <2 seconds on LAN connection
- [ ] Optional HTTPS active when `TLS_CERT_PATH` + `TLS_KEY_PATH` configured

---

## Dependencies

### Blocked By
| Dependency | Type | Status |
|------------|------|--------|
| EP0001 complete | Epic | Must be Done |
| EP0002 complete | Epic | Must be Done — Deco topology, notification config |
| EP0003 complete | Epic | Must be Done — pfSense + AdGuard panels |
| EP0004 complete | Epic | Must be Done — identification, categorisation, lifecycle UI |
| EP0005 complete | Epic | Must be Done — availability monitoring UI |
| EP0006 complete | Epic | Must be Done — speed history page |

### Blocking
| Item | Impact |
|------|--------|
| None — this is the final phase epic | — |

---

## Risks & Assumptions

### Assumptions
- react-flow (or d3-force) is sufficient for the network map without a dedicated graph database
- shadcn/ui components cover all required UI patterns; minimal custom component development needed

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Network map layout is poor when device count is high (100+ nodes) | Medium | Medium | Implement category-based clustering; make map optional/collapsible; default to table view |
| Settings page credential re-entry flow is complex (Docker secrets can't be read back) | High | Medium | Settings page shows "configured" status from system_config flags; re-entry updates Docker secret file via API (write to /run/secrets/ equivalent volume); clearly document |
| React bundle size grows large with Recharts + react-flow | Low | Low | Code splitting via Vite; lazy load chart and map pages |

---

## Technical Considerations

### Architecture Impact
- `frontend/` — all React components expanded from scaffold
- React Router for page navigation (device table, device detail, network map, speed history, events, settings)
- Recharts for speed history chart and availability sparklines
- react-flow or d3 for network map
- `GET /api/v1/system/config` endpoint: returns current config with credentials redacted; `PATCH /api/v1/system/config` updates non-secret settings
- FastAPI `StaticFiles` mount of React build output; Dockerfile COPY from frontend build stage

### Integration Points
- All data consumed from existing REST API endpoints (no new backend data — frontend wires up existing endpoints)
- Settings PATCH → `system_config` table in DB

---

## Sizing

**Story Points:** 34
**Estimated Story Count:** 8

**Complexity Factors:**
- Device detail page has six tabs pulling from multiple data sources
- Network map is the most complex frontend component (graph layout algorithm, zoom/pan, click interactions)
- Settings page must handle 20+ config fields with validation, credential redaction, and persistence
- Responsive layout across all pages adds incremental effort to every component

---

## Story Breakdown

- [ ] US0038: Full device table (all columns, sort, filter by category/owner/status, lifecycle toggle, inline editing)
- [ ] US0039: Device table bulk actions (multi-select, bulk archive, bulk delete with confirmation)
- [ ] US0040: Device detail page — Overview + Network + Traffic tabs
- [ ] US0041: Device detail page — DNS + Availability + Events tabs
- [ ] US0042: Network map (Deco topology + device nodes, react-flow/d3, click-to-navigate)
- [ ] US0043: Events timeline (full filtering, speed event annotations, pagination)
- [ ] US0044: Settings page (all integration config, notification routing, scan/speed/retention settings)
- [ ] US0045: Mobile responsiveness pass + optional HTTPS + PWA manifest + production Dockerfile (multi-stage build, React build → FastAPI StaticFiles)

---

## Open Questions

- [ ] Should the network map use react-flow (declarative, easier) or d3-force (more control over layout)? Recommended: react-flow for v1.0; d3 if layout quality is insufficient. — Owner: Implementation decision
- [ ] Should settings credentials be stored in `system_config` (SQLite, encrypted) or remain Docker-secrets-only? Recommended: Docker secrets for sensitive credentials; `system_config` for non-sensitive settings (intervals, thresholds, toggles). Credential re-entry in UI writes to Docker secret volume mount. — Owner: Implementation decision

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft from PRD v1.1 + TRD v1.0 |
