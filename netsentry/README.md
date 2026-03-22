# NetSentry

**Self-Hosted Network Intelligence Platform**

NetSentry is a continuously-running Docker Compose stack that gives you complete visibility into every device on your home network. It combines active local network scanning with deep integration into pfSense firewalls, TP-Link Deco mesh systems, and AdGuard Home DNS — and delivers real-time push notifications to your phone via ntfy or Telegram.

> **Status:** Phase 1 — Foundation (US0001 in progress)

---

## Features

- **Active Network Scanning** — ARP sweeps, ICMP pings, TCP port probes, mDNS/SSDP listeners, NetBIOS queries, OS fingerprinting
- **TP-Link Deco Integration** — Per-device AP node, Wi-Fi band, real-time wireless throughput, mesh topology
- **pfSense Integration** — DHCP leases, ARP table, per-device traffic stats, firewall rule references, VLAN membership, WAN health
- **AdGuard Home Integration** — Per-device DNS profiles, blocked domain stats, suspicious query detection
- **Device Identification** — Multi-source heuristic fingerprinting + optional AI enrichment via Claude API
- **Device Categorisation** — Controlled vocabulary (Personal Device, Server, Network Infrastructure, Smart Home, etc.) with owner assignment
- **Real-Time Availability Monitoring** — Per-device ICMP/TCP/HTTP probing at 10–30 second intervals
- **Internet Speed Monitor** — Scheduled speed tests via LibreSpeed (self-hosted) or Ookla
- **Push Notifications** — ntfy (Android/iOS) and Telegram Bot API
- **Device Lifecycle** — Archive (historic/hidden) or permanently delete devices
- **Web Dashboard** — React SPA with device table, network map, events timeline, speed history

---

## Quick Start

### Prerequisites

- Docker Engine ≥ 24 with Docker Compose v2
- Linux host (macOS/Windows: see [macvlan alternative](#macvlan))
- TP-Link Deco owner credentials
- pfSense with [pfSense REST API](https://pfrest.org) package installed
- AdGuard Home instance

### 1. Clone and configure

```bash
git clone https://github.com/zoobuv101/NetSentry.git
cd NetSentry
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start the stack

```bash
docker compose up -d
```

### 3. Open the dashboard

```
http://<your-host-ip>:8080
```

### 4. Check health

```bash
curl http://localhost:8080/api/v1/system/health
# {"status":"ok","version":"0.1.0"}
```

---

## Configuration

All configuration is via environment variables in `.env`. See [`.env.example`](.env.example) for the full reference with documentation.

### Required for each integration

| Integration | Required Variables |
|------------|-------------------|
| TP-Link Deco | `DECO_HOST`, `DECO_USERNAME`, `DECO_PASSWORD` |
| pfSense | `PFSENSE_API_URL`, `PFSENSE_API_KEY` |
| AdGuard Home | `ADGUARD_URL`, `ADGUARD_USERNAME`, `ADGUARD_PASSWORD` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| AI Identification | `ANTHROPIC_API_KEY`, `ENABLE_AI_IDENTIFICATION=true` |

---

## Architecture

NetSentry runs as a **modular monolith** — a single Python 3.12 process (FastAPI + APScheduler) plus co-deployed Docker services (ntfy, optional LibreSpeed, optional Redis).

```
netsentry container (network_mode: host, CAP_NET_RAW)
├── FastAPI REST API          :8080
├── APScheduler
│   ├── Scanner Engine        (ARP/ICMP/TCP/mDNS/SSDP — every 5 min)
│   ├── Deco Poller           (every 30s)
│   ├── pfSense Poller        (every 30s)
│   ├── AdGuard Poller        (every 60s)
│   ├── Availability Monitor  (per-device, 10–30s)
│   └── Speed Monitor         (every 6h)
├── Event Engine → Notification Engine → ntfy / Telegram
└── SQLite /data/netsentry.db
```

See [docs/architecture.md](docs/architecture.md) for the full TRD and C4 diagrams.

---

## Development

```bash
# Install dependencies (requires uv)
pip install uv
uv pip install -e ".[dev]"

# Run tests (TDD — write tests first)
pytest

# Lint + format
ruff check . && ruff format .

# Type check
mypy netsentry/

# Start dev stack (hot-reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

---

## Optional Profiles

```bash
# Include self-hosted LibreSpeed speed test server
docker compose --profile librespeed up -d

# Include Redis cache (for >150 device networks)
docker compose --profile redis up -d

# Both
docker compose --profile librespeed --profile redis up -d
```

---

## macvlan Alternative

If `network_mode: host` is unavailable (Docker Desktop on macOS/Windows, or VMs), use a macvlan network to give the scanner container its own MAC address on the LAN. See [docs/macvlan.md](docs/macvlan.md) for setup instructions.

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 — Foundation | 🚧 In Progress | Docker stack, scanner, device inventory, basic API |
| 2 — Deco + Notifications | ⏳ Planned | Deco mesh integration, ntfy + Telegram alerts |
| 3 — pfSense + AdGuard | ⏳ Planned | Firewall and DNS intelligence |
| 4 — Polish | ⏳ Planned | AI identification, availability monitoring, speed tests, full dashboard |
| 5 — Advanced | 🔮 Future | FW_agent integration, voice interface, Home Assistant, Prometheus |

---

## License

MIT — see [LICENSE](LICENSE).
