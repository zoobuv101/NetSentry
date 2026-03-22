# EP0004: Device Identification, Categorisation & Lifecycle Management

> **Status:** Draft
> **Phase:** 4 — AdGuard + Polish (identification and device management)
> **Created:** 2026-03-21
> **PRD Reference:** [PRD](../prd.md) · [TRD](../trd.md)

## Summary

Builds the multi-source device identification pipeline (MAC OUI, open port patterns, mDNS/SSDP service types, OS fingerprint, DNS query patterns, Deco device type — combined into a weighted confidence score), adds optional AI enrichment via the Claude API for low-confidence devices, implements the full device categorisation and ownership model (controlled vocabulary categories, subcategories, owner, friendly name, notes), and delivers device lifecycle management (archive to Historic, permanent delete with audit log). After this epic every device can be named, categorised, assigned to a household member, and retired cleanly.

---

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| TRD ADR-005 | AI | `ENABLE_AI_IDENTIFICATION=false` default; explicit opt-in; non-PII signals only | AI must be gated; no IPs/user-assigned names sent to Claude API |
| PRD | AI | Max 10 Claude API calls per scan cycle; only below confidence threshold (default 0.6) | Rate limiting and confidence check required before every AI call |
| PRD | UX | Manual overrides (`source: manual`) never overwritten by automatic processes | `manually_set` flag must be checked before any auto-update |
| PRD | Lifecycle | Permanent delete is irreversible; requires `confirm=<mac>` in API | UI must enforce type-to-confirm dialog |
| TRD | Data | `IdentificationResult` table with source attribution; `DeletionAuditLog` retained permanently | Alembic migration required |

---

## Business Context

### Problem Statement
After EP0001–EP0003 the inventory is full of devices with MAC addresses and IPs but no meaningful labels. The operator must manually look up every device to understand what it is. There is also no way to assign devices to household members, categorise them by type, or retire devices that have left the network permanently.

**PRD Reference:** PRD §3 — Device Identification & Classification; Device Categorisation & Ownership; Device Inventory History & Lifecycle

### Value Proposition
Every newly joined device is automatically identified (product type, OS, manufacturer) using all available signals. The operator can accept, override, and enrich the identification with a friendly name, category, and owner. Retired devices can be archived (hidden but retained) or permanently deleted, keeping the active view clean.

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Auto-identification rate | ≥80% of common device types correctly classified by heuristics alone | Manual audit of 20 common devices |
| AI identification improvement | AI correctly identifies ≥70% of devices that heuristics score <0.6 | Test set of 10 ambiguous devices |
| Manual override persistence | 100% of manual overrides survive scan cycles | Set 5 manual overrides; run 3 scan cycles; verify unchanged |
| Historic device hidden | 100% of Historic devices absent from default `GET /devices` | Set 3 devices Historic; verify not in default list |
| Deletion audit | DeletionAuditLog entry created for every permanent delete | Delete 2 devices; verify log entries |

---

## Scope

### In Scope
- Identification Pipeline module (`netsentry/identification/`): heuristic engine, signal collector, confidence scorer
- Heuristic signals: MAC OUI pattern matching, open port pattern map, mDNS service type map, SSDP/UPnP device type, nmap OS fingerprint, AdGuard DNS domain patterns, Deco device type
- Confidence scoring: weighted combination of all signals; configurable weights
- AI enrichment module: Claude API call (claude-haiku default), rate limiter (max 10/cycle), confidence gate (skip if ≥0.6), signal fingerprint cache (skip if identical to last call), non-PII payload builder
- `identification_results` table (Alembic migration): source, product_type, os_family, os_version, manufacturer, model_guess, confidence, reasoning, manually_set
- Identification pipeline runs on every new device and weekly on existing low-confidence devices
- PATCH `/api/v1/devices/{mac}` accepts `category`, `subcategory`, `owner`, `friendly_name`, `notes`, `lifecycle` fields
- Device categorisation: controlled vocabulary (10 categories, predefined subcategories per category), `custom_subcategories` table
- Ownership: `owner` field (free text) per device
- Device lifecycle state machine: `active` → `historic` (PATCH lifecycle=historic) → `active` (PATCH lifecycle=active) and `active` → deleted (DELETE endpoint)
- DELETE `/api/v1/devices/{mac}?confirm={mac}`: permanent purge of device + all sub-records; `deletion_audit_log` entry created
- `GET /api/v1/devices` supports `?lifecycle=historic` filter; default returns active only
- Dashboard device table: "Show historic" toggle; historic devices with muted style + badge
- Bulk archive and bulk delete (multi-select in UI → batch PATCH/DELETE API calls)
- Device detail page: identification result panel (signals + confidence breakdown + AI reasoning), category/owner/notes inline editing
- Settings UI: AI identification toggle, API key config, confidence threshold slider

### Out of Scope
- Availability monitoring (EP0005)
- Speed testing (EP0006)
- Full dashboard polish (EP0007)

### Affected Personas
- **Primary Operator:** Gains named, organised device inventory; can assign household ownership
- **Household Members:** Can be named as device owners; may view clean categorised device list

---

## Acceptance Criteria (Epic Level)

- [ ] Identification pipeline runs automatically on every new device discovered
- [ ] MAC OUI, open port patterns, mDNS service types, SSDP/UPnP type, OS fingerprint, and DNS query patterns all contribute to the confidence score
- [ ] Devices above confidence threshold (default 0.6) are NOT sent to the Claude API even when AI is enabled
- [ ] When `ENABLE_AI_IDENTIFICATION=false` (default), no calls are made to the Anthropic API under any circumstances
- [ ] When AI is enabled, max 10 calls per scan cycle enforced; identical signal fingerprint does not trigger a re-call
- [ ] AI identification result stored in `identification_results` with `source: ai` and reasoning JSON
- [ ] Manual override stored with `source: manual` and `manually_set: true`; never overwritten by subsequent scan cycles
- [ ] Device `category`, `subcategory`, `owner`, `friendly_name`, `notes` all patchable via `PATCH /api/v1/devices/{mac}`
- [ ] All 10 predefined categories and their subcategories available in UI dropdowns
- [ ] Custom subcategories creatable by user and persisted
- [ ] `friendly_name` overrides hostname in all UI display contexts
- [ ] Setting lifecycle to `historic` removes device from default `GET /devices` response
- [ ] Historic devices reappearing on the network are silently re-activated (lifecycle → active) with an informational event; no new-device alert fires
- [ ] `DELETE /api/v1/devices/{mac}?confirm={mac}` permanently purges device and all sub-records
- [ ] `deletion_audit_log` entry (mac, deleted_at, friendly_name_at_deletion) created on every permanent delete
- [ ] Permanently deleted device MAC reappearing on the network is treated as brand-new
- [ ] UI deletion dialog requires user to type MAC or friendly name before enabling the Delete button
- [ ] Bulk archive and bulk delete work correctly for multi-selected devices

---

## Dependencies

### Blocked By
| Dependency | Type | Status |
|------------|------|--------|
| EP0001 complete | Epic | Must be Done — scanner signals required |
| EP0002 complete | Epic | Must be Done — Deco device type signal required |
| EP0003 complete | Epic | Must be Done — AdGuard DNS signal required for full identification |
| Anthropic API key (optional) | Operator config | Required only if `ENABLE_AI_IDENTIFICATION=true` |

### Blocking
| Item | Impact |
|------|--------|
| EP0007 (Full Dashboard) | Category/owner filtering and lifecycle toggle in dashboard |

---

## Risks & Assumptions

### Assumptions
- Common device types (phones, laptops, smart TVs, printers, routers) are identifiable from MAC OUI + port patterns + mDNS with confidence ≥0.6 without AI
- Claude haiku model is sufficiently capable for structured device classification JSON output
- AdGuard dns_profiles are populated (EP0003) before identification pipeline runs for full signal coverage

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Claude API cost exceeds expectation if many new devices join | Low | Medium | Hard cap of 10 calls/cycle; signal fingerprint cache prevents re-calls; operator can lower confidence threshold to reduce AI calls |
| Heuristic identification misclassifies devices with unusual port combinations | Medium | Low | Confidence score surfaced in UI; operator can manually override; misclassification is non-blocking |
| Permanent deletion of wrong device | Medium | High | Type-to-confirm UI; `confirm=<mac>` required in API; deletion_audit_log always retained |
| Deco or AdGuard signals not yet available when identification runs (EP0002/EP0003 not done) | N/A — resolved by dependency order | — | EP0004 is blocked by EP0002 and EP0003 |

---

## Technical Considerations

### Architecture Impact
- `netsentry/identification/` package: `pipeline.py` (orchestration), `heuristics.py` (signal scoring), `ai.py` (Claude API client, rate limiter, cache), `signals.py` (signal collector from DB), `port_patterns.py` (port→device type map), `dns_patterns.py` (domain→vendor map), `mdns_patterns.py` (service type→category map)
- `netsentry/db/repositories/identification.py`: CRUD for `identification_results`
- Alembic migration 0004: `identification_results`, `custom_subcategories`, `deletion_audit_log`
- PATCH handler on `devices` endpoint validates category/subcategory against controlled vocabulary
- Event Engine extended: device lifecycle change events (archived, restored, deleted)

### Integration Points
- Anthropic Claude API: HTTPS POST to `api.anthropic.com/v1/messages` (optional, gated)
- All identification signals sourced from existing DB tables (no new external calls)

---

## Sizing

**Story Points:** 31
**Estimated Story Count:** 7

**Complexity Factors:**
- Heuristic engine requires comprehensive port pattern and DNS domain maps (research effort)
- AI enrichment module requires careful rate limiting, caching, and non-PII payload construction
- Lifecycle state machine has edge cases (re-activation of historic devices, cascade delete integrity)
- Controlled vocabulary enforcement at API layer + custom subcategory extension

---

## Story Breakdown

- [ ] US0022: Identification pipeline scaffold + heuristic engine (MAC OUI, port patterns, mDNS/SSDP/UPnP signal maps)
- [ ] US0023: Heuristic signal integration (OS fingerprint, AdGuard DNS patterns, Deco device type; confidence scoring)
- [ ] US0024: AI enrichment module (Claude API client, rate limiter, confidence gate, signal fingerprint cache, non-PII payload)
- [ ] US0025: `identification_results` DB table + pipeline scheduler integration + manual override support
- [ ] US0026: Device categorisation model (PATCH endpoint, controlled vocabulary, custom_subcategories, owner/friendly_name/notes)
- [ ] US0027: Device lifecycle management (historic state, re-activation logic, permanent delete endpoint + audit log)
- [ ] US0028: Identification UI (device detail panel: signals + confidence + AI reasoning) + categorisation UI (inline editing, dropdowns) + lifecycle UI (Show historic toggle, bulk actions, delete confirmation dialog)

---

## Open Questions

- [ ] Should the port pattern map and DNS domain map be bundled in-code or loaded from YAML/JSON config files (allowing operator customisation without code changes)? Recommended: YAML files shipped with the image, overridable via volume mount. — Owner: Implementation decision
- [ ] Should AI identification be triggered immediately on new device discovery (within the scan cycle) or on a separate delayed job to avoid slowing down scan completion? Recommended: separate deferred APScheduler job, 5-minute delay after discovery. — Owner: Implementation decision

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft from PRD v1.1 + TRD v1.0 |
