import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/api/client";
import type { EventLogEntry } from "@/types/api";

const SEVERITY_STYLES: Record<string, string> = {
  urgent: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  high:   "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  info:   "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  low:    "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

const EVENT_TYPE_OPTIONS = [
  { value: "",                  label: "All types" },
  { value: "device.new",        label: "New device" },
  { value: "device.offline",    label: "Device offline" },
  { value: "device.online",     label: "Device online" },
  { value: "availability.down", label: "Unreachable" },
  { value: "availability.up",   label: "Reachable again" },
  { value: "system.scan_failed",label: "Scan failed" },
  { value: "speed.slow",        label: "Speed degraded" },
];

const PAGE_SIZE = 100;

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "short",
      timeStyle: "medium",
    }).format(new Date(iso));
  } catch { return iso; }
}

function deviceLabel(e: EventLogEntry): string {
  if (e.device?.friendly_name) return e.device.friendly_name;
  if (e.device?.hostname)      return e.device.hostname;
  if (e.mac_address)           return e.mac_address;
  return "System";
}

function detailSummary(e: EventLogEntry): string {
  const d = e.details;
  if (!d || Object.keys(d).length === 0) return "";
  if (d.last_ip)            return `Last IP: ${d.last_ip}`;
  if (d.ip)                 return `IP: ${d.ip}`;
  if (d.download_mbps)      return `${(d.download_mbps as number).toFixed(0)} Mbps down`;
  if (d.consecutive_failures) return `${d.consecutive_failures} missed probes`;
  return Object.entries(d).slice(0, 2).map(([k, v]) => `${k}: ${v}`).join(", ");
}

export function AlertsPage() {
  const [events, setEvents]   = useState<EventLogEntry[]>([]);
  const [total, setTotal]     = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [query, setQuery]     = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [eventType, setEventType]   = useState("");
  const [offset, setOffset]  = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Debounce search input 300ms
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQ(query);
      setOffset(0);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getEvents({
        q: debouncedQ || undefined,
        event_type: eventType || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setEvents(res.events);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load events");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, eventType, offset]);

  useEffect(() => { load(); }, [load]);

  const pages = Math.ceil(total / PAGE_SIZE);
  const page  = Math.floor(offset / PAGE_SIZE);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Alert Log</h1>
          {!loading && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {total.toLocaleString()} event{total !== 1 ? "s" : ""}
              {(debouncedQ || eventType) ? " matching filters" : " total"}
            </p>
          )}
        </div>
        <button onClick={load}
          className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 underline">
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, IP, MAC, vendor…"
            className="w-full pl-8 pr-7 py-1.5 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {query && (
            <button onClick={() => setQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">×</button>
          )}
        </div>

        {/* Event type filter */}
        <select
          value={eventType}
          onChange={(e) => { setEventType(e.target.value); setOffset(0); }}
          className="text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {EVENT_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {(debouncedQ || eventType) && (
          <button
            onClick={() => { setQuery(""); setEventType(""); setOffset(0); }}
            className="text-xs text-blue-600 dark:text-blue-400 underline whitespace-nowrap"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      {error ? (
        <div className="rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-gray-400">Loading…</div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2 text-sm text-gray-500">
          <span>No events found.</span>
          {(debouncedQ || eventType) && (
            <button onClick={() => { setQuery(""); setEventType(""); }}
              className="text-blue-500 underline text-xs">Clear filters</button>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {["Time", "Event", "Device", "IP / MAC", "Detail", "Notified"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900">
              {events.map((e) => (
                <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                  {/* Time */}
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap font-mono">
                    {formatDate(e.timestamp)}
                  </td>
                  {/* Event type */}
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${SEVERITY_STYLES[e.severity] ?? SEVERITY_STYLES.low}`}>
                        {e.severity}
                      </span>
                      <span className="text-gray-700 dark:text-gray-300 text-xs">{e.event_label}</span>
                    </div>
                  </td>
                  {/* Device */}
                  <td className="px-4 py-3">
                    <span className="font-medium text-gray-900 dark:text-gray-100">{deviceLabel(e)}</span>
                    {e.device?.vendor && (
                      <div className="text-xs text-gray-400 mt-0.5">{e.device.vendor}</div>
                    )}
                  </td>
                  {/* IP / MAC */}
                  <td className="px-4 py-3 font-mono text-xs text-gray-600 dark:text-gray-300">
                    {e.device?.current_ip && <div>{e.device.current_ip}</div>}
                    {e.mac_address && <div className="opacity-60">{e.mac_address}</div>}
                  </td>
                  {/* Detail */}
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 max-w-[200px] truncate">
                    {detailSummary(e)}
                  </td>
                  {/* Notified */}
                  <td className="px-4 py-3 text-center">
                    {e.notification_sent ? (
                      <span className="text-green-600 dark:text-green-400 text-xs" title="Notification sent">✓</span>
                    ) : (
                      <span className="text-gray-300 dark:text-gray-600 text-xs">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <span>Page {page + 1} of {pages} ({total.toLocaleString()} events)</span>
          <div className="flex gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={offset === 0}
              className="rounded px-3 py-1.5 border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              ← Prev
            </button>
            <button
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={offset + PAGE_SIZE >= total}
              className="rounded px-3 py-1.5 border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
