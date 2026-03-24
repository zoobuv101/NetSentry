import { useState, useMemo } from "react";
import type { Device } from "@/types/api";

type SortKey = "name" | "ip" | "mac" | "vendor" | "status" | "last_seen";
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
      <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
      Online
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
      <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
      Offline
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function deviceName(d: Device): string {
  return d.friendly_name ?? d.hostname ?? d.mac_address;
}

function isNewToday(d: Device): boolean {
  try {
    const created = new Date(d.first_seen);
    const now = new Date();
    return (
      created.getFullYear() === now.getFullYear() &&
      created.getMonth() === now.getMonth() &&
      created.getDate() === now.getDate()
    );
  } catch {
    return false;
  }
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "name",      label: "Name" },
  { key: "ip",        label: "IP Address" },
  { key: "mac",       label: "MAC" },
  { key: "vendor",    label: "Vendor" },
  { key: "status",    label: "Status" },
  { key: "last_seen", label: "Last Seen" },
];

function SortIcon({ dir }: { dir: SortDir | null }) {
  if (!dir) return (
    <span className="ml-1 opacity-30 text-[10px]">↕</span>
  );
  return <span className="ml-1 text-[10px]">{dir === "asc" ? "↑" : "↓"}</span>;
}

export function DeviceTable({ devices, loading, error, initialFilter = "", initialStatus = null }: Props) {
  const [filter, setFilter] = useState(initialFilter);
  const [sortKey, setSortKey] = useState<SortKey>("status");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [statusFilter, setStatusFilter] = useState<"online" | "offline" | "new_today" | null>(initialStatus);

  // Sync if parent changes initialFilter (dashboard deep-link)
  // Use a ref-based approach via key instead — handled by parent remounting

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "last_seen" ? "desc" : "asc");
    }
  }

  const filtered = useMemo(() => {
    let result = [...devices];

    // Status filter (from dashboard deep-link or local toggle)
    if (statusFilter === "online") {
      result = result.filter((d) => d.is_online);
    } else if (statusFilter === "offline") {
      result = result.filter((d) => !d.is_online);
    } else if (statusFilter === "new_today") {
      result = result.filter(isNewToday);
    }

    // Text filter
    if (filter.trim()) {
      const q = filter.trim().toLowerCase();
      result = result.filter(
        (d) =>
          deviceName(d).toLowerCase().includes(q) ||
          (d.current_ip ?? "").includes(q) ||
          d.mac_address.toLowerCase().includes(q) ||
          (d.vendor ?? "").toLowerCase().includes(q)
      );
    }

    // Sort
    result.sort((a, b) => {
      let va = "", vb = "";
      switch (sortKey) {
        case "name":      va = deviceName(a).toLowerCase(); vb = deviceName(b).toLowerCase(); break;
        case "ip":        va = a.current_ip ?? ""; vb = b.current_ip ?? ""; break;
        case "mac":       va = a.mac_address; vb = b.mac_address; break;
        case "vendor":    va = a.vendor ?? ""; vb = b.vendor ?? ""; break;
        case "status":    va = a.is_online ? "1" : "0"; vb = b.is_online ? "1" : "0"; break;
        case "last_seen": va = a.last_seen; vb = b.last_seen; break;
      }
      const cmp = va.localeCompare(vb, undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });

    return result;
  }, [devices, filter, sortKey, sortDir, statusFilter]);

  const statusPills = [
    { key: null,         label: "All" },
    { key: "online",     label: "Online" },
    { key: "offline",    label: "Offline" },
    { key: "new_today",  label: "New today" },
  ] as const;

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
        <strong>Error loading devices:</strong> {error}
        <button className="ml-3 underline hover:no-underline" onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-1.5 flex-wrap">
          {statusPills.map((p) => (
            <button
              key={String(p.key)}
              onClick={() => setStatusFilter(p.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                statusFilter === p.key
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z" />
          </svg>
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by name, IP, MAC, vendor…"
            className="pl-8 pr-8 py-1.5 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
          />
          {filter && (
            <button
              onClick={() => setFilter("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              aria-label="Clear filter"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Result count */}
      {!loading && (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {filtered.length === devices.length
            ? `${devices.length} device${devices.length !== 1 ? "s" : ""}`
            : `${filtered.length} of ${devices.length} device${devices.length !== 1 ? "s" : ""}`}
        </p>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-gray-500 dark:text-gray-400">
          Loading devices…
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2 text-sm text-gray-500 dark:text-gray-400">
          <span>{devices.length === 0 ? "No devices found. Waiting for first scan…" : "No devices match your filter."}</span>
          {(filter || statusFilter) && (
            <button
              onClick={() => { setFilter(""); setStatusFilter(null); }}
              className="text-blue-500 underline text-xs"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200 whitespace-nowrap"
                  >
                    {col.label}
                    <SortIcon dir={sortKey === col.key ? sortDir : null} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900">
              {filtered.map((device) => (
                <tr key={device.mac_address} className="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                    {deviceName(device)}
                    {isNewToday(device) && (
                      <span className="ml-2 rounded-full bg-blue-100 dark:bg-blue-900/30 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:text-blue-400">new</span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-700 dark:text-gray-300">
                    {device.current_ip ?? "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-500 dark:text-gray-400 text-xs">
                    {device.mac_address}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {device.vendor ?? "—"}
                  </td>
                  <td className="px-4 py-3">{statusBadge(device.is_online)}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                    {formatDate(device.last_seen)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
