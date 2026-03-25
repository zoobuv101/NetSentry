import React, { useState, useMemo, useEffect } from "react";
import { api } from "@/api/client";
import type { Device } from "@/types/api";

type SortKey = "name" | "ip" | "mac" | "vendor" | "status" | "os" | "last_seen";
type SortDir = "asc" | "desc";

interface Props {
  devices: Device[];
  loading: boolean;
  error: string | null;
  initialFilter?: string;
  initialStatus?: "online" | "offline" | "new_today" | null;
}

function statusBadge(online: boolean) {
  return online ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
      <span className="h-1.5 w-1.5 rounded-full bg-green-500" />Online
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
      <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />Offline
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(iso));
  } catch { return iso; }
}

function deviceName(d: Device): string {
  return d.friendly_name ?? d.netbios_name ?? d.hostname ?? d.mac_address;
}

function deviceOs(d: Device): string | null {
  if (!d.os_family) return null;
  return d.os_version ? `${d.os_family} ${d.os_version}` : d.os_family;
}

function deviceCategory(d: Device): string | null {
  return d.device_type ?? d.category ?? d.ssdp_device_type ?? null;
}

function isNewToday(d: Device): boolean {
  try {
    const created = new Date(d.first_seen);
    const now = new Date();
    return created.getFullYear() === now.getFullYear() &&
      created.getMonth() === now.getMonth() &&
      created.getDate() === now.getDate();
  } catch { return false; }
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "name",      label: "Name" },
  { key: "ip",        label: "IP" },
  { key: "vendor",    label: "Vendor / Category" },
  { key: "os",        label: "OS" },
  { key: "status",    label: "Status" },
  { key: "last_seen", label: "Last Seen" },
];

function SortIcon({ dir }: { dir: SortDir | null }) {
  return <span className={`ml-1 text-[10px] ${dir ? "opacity-80" : "opacity-30"}`}>{!dir ? "↕" : dir === "asc" ? "↑" : "↓"}</span>;
}

// ── Expandable detail row ─────────────────────────────────────────────────────
function DeviceDetailRow({ device, onAlertsToggle }: {
  device: Device;
  onAlertsToggle: (mac: string, enabled: boolean) => void;
}) {
  const hasPorts = device.open_ports.length > 0;
  const hasServices = device.services.length > 0;
  const hasMdns = device.mdns_services.length > 0;

  if (!hasPorts && !hasMdns && !device.netbios_name && !device.ssdp_device_type && !device.os_family) {
    return (
      <tr className="bg-gray-50 dark:bg-gray-800/50">
        <td colSpan={6} className="px-6 py-2 text-xs text-gray-400 dark:text-gray-500 italic">
          No enrichment data yet — run a Standard or Deep scan to collect port and OS info.
        </td>
      </tr>
    );
  }

  return (
    <tr className="bg-gray-50 dark:bg-gray-800/50">
      <td colSpan={6} className="px-6 py-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 text-xs">

          {/* Identity */}
          <div>
            <p className="font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Identity</p>
            <div className="space-y-0.5">
              <p className="font-mono text-gray-600 dark:text-gray-300">{device.mac_address}</p>
              {device.netbios_name && <p>NetBIOS: <span className="font-medium">{device.netbios_name}</span></p>}
              {device.ssdp_device_type && <p>UPnP: <span className="font-medium">{device.ssdp_device_type}</span></p>}
              {device.os_family && (
                <p>OS: <span className="font-medium">{deviceOs(device)}</span>
                  {device.last_os_scan && <span className="opacity-50 ml-1">(scanned {formatDate(device.last_os_scan)})</span>}
                </p>
              )}
              {/* Alerts toggle */}
              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={() => onAlertsToggle(device.mac_address, !device.alerts_enabled)}
                  className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${
                    device.alerts_enabled
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/50"
                      : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
                  }`}
                  title={device.alerts_enabled ? "Alerts on — click to silence this device" : "Alerts off — click to enable"}
                >
                  <span>{device.alerts_enabled ? "🔔" : "🔕"}</span>
                  {device.alerts_enabled ? "Alerts on" : "Alerts silenced"}
                </button>
              </div>
            </div>
          </div>

          {/* Open ports */}
          {hasPorts && (
            <div>
              <p className="font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                Open Ports
                {device.last_port_scan && <span className="normal-case font-normal ml-1 opacity-50">(scanned {formatDate(device.last_port_scan)})</span>}
              </p>
              <div className="flex flex-wrap gap-1">
                {device.open_ports.map((port) => {
                  const svc = device.services.find((s) => s.port === port);
                  return (
                    <span key={port} className="rounded bg-blue-100 dark:bg-blue-900/30 px-1.5 py-0.5 font-mono text-blue-700 dark:text-blue-300"
                      title={svc ? `${svc.service ?? ""}${svc.version ? " — " + svc.version : ""}` : undefined}>
                      {port}{svc?.service ? `/${svc.service}` : ""}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* Services detail */}
          {hasServices && (
            <div>
              <p className="font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Services</p>
              <div className="space-y-0.5">
                {device.services.filter(s => s.version || s.service).map((svc) => (
                  <p key={svc.port} className="text-gray-600 dark:text-gray-300">
                    <span className="font-mono text-blue-600 dark:text-blue-400">{svc.port}</span>
                    {svc.service && <span className="mx-1 text-gray-500">·</span>}
                    {svc.service && <span className="font-medium">{svc.service}</span>}
                    {svc.version && <span className="opacity-60 ml-1">{svc.version}</span>}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* mDNS */}
          {hasMdns && (
            <div>
              <p className="font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">mDNS Services</p>
              <div className="space-y-0.5">
                {device.mdns_services.map((svc) => (
                  <p key={svc} className="font-mono text-gray-600 dark:text-gray-300">{svc}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

// ── Main table ────────────────────────────────────────────────────────────────
export function DeviceTable({ devices, loading, error, initialFilter = "", initialStatus = null }: Props) {
  const [filter, setFilter] = useState(initialFilter);
  const [sortKey, setSortKey] = useState<SortKey>("status");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [statusFilter, setStatusFilter] = useState<"online" | "offline" | "new_today" | null>(initialStatus);
  const [expandedMac, setExpandedMac] = useState<string | null>(null);
  // Optimistic overrides for alerts_enabled — keyed by mac_address
  const [alertOverrides, setAlertOverrides] = useState<Record<string, boolean>>({});

  // Sync statusFilter when the prop changes (e.g. navigating from dashboard)
  useEffect(() => {
    setStatusFilter(initialStatus);
  }, [initialStatus]);

  async function handleAlertsToggle(mac: string, enabled: boolean) {
    setAlertOverrides(prev => ({ ...prev, [mac]: enabled }));
    try {
      await api.patchDevice(mac, { alerts_enabled: enabled });
    } catch {
      // Revert on failure
      setAlertOverrides(prev => ({ ...prev, [mac]: !enabled }));
    }
  }

  function handleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir(key === "last_seen" ? "desc" : "asc"); }
  }

  // Merge alertOverrides into devices — devices prop is the source of truth
  const mergedDevices = useMemo(
    () => devices.map(d =>
      d.mac_address in alertOverrides
        ? { ...d, alerts_enabled: alertOverrides[d.mac_address] }
        : d
    ),
    [devices, alertOverrides]
  );

  const filtered = useMemo(() => {
    let result = [...mergedDevices];
    if (statusFilter === "online") result = result.filter(d => d.is_online);
    else if (statusFilter === "offline") result = result.filter(d => !d.is_online);
    else if (statusFilter === "new_today") result = result.filter(isNewToday);

    if (filter.trim()) {
      const q = filter.trim().toLowerCase();
      result = result.filter(d =>
        deviceName(d).toLowerCase().includes(q) ||
        (d.current_ip ?? "").includes(q) ||
        d.mac_address.toLowerCase().includes(q) ||
        (d.vendor ?? "").toLowerCase().includes(q) ||
        (d.os_family ?? "").toLowerCase().includes(q) ||
        (d.category ?? "").toLowerCase().includes(q) ||
        (d.device_type ?? "").toLowerCase().includes(q) ||
        (d.netbios_name ?? "").toLowerCase().includes(q) ||
        d.open_ports.some(p => String(p).includes(q))
      );
    }

    result.sort((a, b) => {
      let va = "", vb = "";
      switch (sortKey) {
        case "name":      va = deviceName(a).toLowerCase(); vb = deviceName(b).toLowerCase(); break;
        case "ip":        va = a.current_ip ?? ""; vb = b.current_ip ?? ""; break;
        case "vendor":    va = (a.vendor ?? a.category ?? "").toLowerCase(); vb = (b.vendor ?? b.category ?? "").toLowerCase(); break;
        case "os":        va = deviceOs(a) ?? ""; vb = deviceOs(b) ?? ""; break;
        case "status":    va = a.is_online ? "1" : "0"; vb = b.is_online ? "1" : "0"; break;
        case "last_seen": va = a.last_seen; vb = b.last_seen; break;
        case "mac":       va = a.mac_address; vb = b.mac_address; break;
      }
      const cmp = va.localeCompare(vb, undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
    return result;
  }, [mergedDevices, filter, sortKey, sortDir, statusFilter]);

  if (error) return (
    <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
      <strong>Error:</strong> {error}
      <button className="ml-3 underline" onClick={() => window.location.reload()}>Retry</button>
    </div>
  );

  const statusPills = [
    { key: null,        label: "All" },
    { key: "online",    label: "Online" },
    { key: "offline",   label: "Offline" },
    { key: "new_today", label: "New today" },
  ] as const;

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-1.5 flex-wrap">
          {statusPills.map((p) => (
            <button key={String(p.key)} onClick={() => setStatusFilter(p.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                statusFilter === p.key
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
              }`}>
              {p.label}
            </button>
          ))}
        </div>
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z" />
          </svg>
          <input type="text" value={filter} onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by name, IP, OS, port…"
            className="pl-8 pr-7 py-1.5 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 w-64" />
          {filter && (
            <button onClick={() => setFilter("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">×</button>
          )}
        </div>
      </div>

      {!loading && (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {filtered.length === devices.length
            ? `${devices.length} device${devices.length !== 1 ? "s" : ""}`
            : `${filtered.length} of ${devices.length}`}
          {" · "}
          <span className="opacity-70">Click a row to see ports &amp; OS detail</span>
        </p>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-gray-500">Loading devices…</div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2 text-sm text-gray-500">
          <span>{devices.length === 0 ? "No devices found. Waiting for first scan…" : "No devices match your filter."}</span>
          {(filter || statusFilter) && (
            <button onClick={() => { setFilter(""); setStatusFilter(null); }} className="text-blue-500 underline text-xs">Clear filters</button>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="w-8" />
                {COLUMNS.map((col) => (
                  <th key={col.key} onClick={() => handleSort(col.key)}
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200 whitespace-nowrap">
                    {col.label}<SortIcon dir={sortKey === col.key ? sortDir : null} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900">
              {filtered.map((device) => (
                <React.Fragment key={device.mac_address}>
                  <tr
                    onClick={() => setExpandedMac(expandedMac === device.mac_address ? null : device.mac_address)}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer">
                    {/* Expand toggle */}
                    <td className="pl-3 pr-1 py-3 text-gray-400">
                      <span className="text-xs">{expandedMac === device.mac_address ? "▾" : "▸"}</span>
                    </td>
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                      <div className="flex items-center gap-1.5">
                        {deviceName(device)}
                        {isNewToday(device) && (
                          <span className="rounded-full bg-blue-100 dark:bg-blue-900/30 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:text-blue-400">new</span>
                        )}
                        {device.open_ports.length > 0 && (
                          <span className="rounded bg-gray-100 dark:bg-gray-700 px-1 py-0.5 text-[10px] text-gray-500 dark:text-gray-400"
                            title={`Open ports: ${device.open_ports.join(", ")}`}>
                            {device.open_ports.length}p
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-700 dark:text-gray-300">{device.current_ip ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      <div>{device.vendor ?? "—"}</div>
                      {deviceCategory(device) && (
                        <div className="text-xs opacity-60 mt-0.5">{deviceCategory(device)}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      {deviceOs(device) ?? <span className="opacity-40">—</span>}
                    </td>
                    <td className="px-4 py-3">{statusBadge(device.is_online)}</td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{formatDate(device.last_seen)}</td>
                  </tr>
                  {expandedMac === device.mac_address && (
                    <DeviceDetailRow key={`${device.mac_address}-detail`} device={device} onAlertsToggle={handleAlertsToggle} />
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
