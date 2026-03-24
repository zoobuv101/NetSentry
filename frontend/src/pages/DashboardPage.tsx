import { useDashboard } from "@/hooks/useDashboard";
import { useFirewallInterfaces } from "@/hooks/useFirewallInterfaces";
import type { InterfaceStatus } from "@/hooks/useFirewallInterfaces";
import { SpeedChart } from "@/components/SpeedChart";
import { EventFeed } from "@/components/EventFeed";
import { api } from "@/api/client";
import { useState } from "react";
import type { Page, DeviceFilter } from "@/App";

interface Props {
  navigate: (page: Page, filter?: DeviceFilter) => void;
}

const gradeColors: Record<string, string> = {
  excellent: "text-green-700 dark:text-green-400",
  good:      "text-green-600 dark:text-green-500",
  fair:      "text-yellow-600 dark:text-yellow-400",
  poor:      "text-red-600 dark:text-red-400",
};

function formatDate(iso: string | null) {
  if (!iso) return null;
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(iso));
  } catch { return iso; }
}

// ── Stat card with consistent muted label colour ──────────────────────────────
interface ClickableStatProps {
  label: string;
  value: string | number | null;
  sub?: string;
  onClick?: () => void;
  valueColor?: string;
}

function ClickableStat({ label, value, sub, onClick, valueColor = "text-gray-800 dark:text-gray-100" }: ClickableStatProps) {
  const clickable = onClick
    ? "cursor-pointer hover:shadow-md hover:scale-[1.02] hover:ring-2 ring-blue-400/30 transition-all"
    : "";
  return (
    <div
      className={`rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4 ${clickable}`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
    >
      {/* Label matches the "Devices" section heading colour */}
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {label}
      </p>
      <p className={`mt-1 text-2xl font-bold ${valueColor}`}>
        {value ?? <span className="text-base font-normal opacity-40">—</span>}
      </p>
      {sub && <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{sub}</p>}
      {onClick && (
        <p className="mt-1.5 text-[10px] text-gray-400 dark:text-gray-500 font-medium tracking-wide">
          VIEW DEVICES →
        </p>
      )}
    </div>
  );
}

// ── Firewall interface card ───────────────────────────────────────────────────
function IfaceCard({ iface }: { iface: InterfaceStatus }) {
  const label = iface.description || iface.name.toUpperCase();
  const isUp = iface.up && iface.running;

  // Abbreviate media string
  const media = iface.media
    ? iface.media.replace("Ethernet ", "").replace(" <full-duplex>", " FD").replace(" <half-duplex>", " HD")
    : null;

  return (
    <div className="flex items-start justify-between py-2.5 border-b border-gray-100 dark:border-gray-800 last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        <div className={`h-2 w-2 rounded-full shrink-0 mt-0.5 ${isUp ? "bg-green-500" : "bg-red-400"}`} />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-800 dark:text-gray-100 truncate">{label}</p>
          <p className="font-mono text-xs text-gray-500 dark:text-gray-400">
            {iface.name}
          </p>
        </div>
      </div>
      <div className="text-right shrink-0 ml-3">
        <p className={`text-xs font-semibold ${isUp ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
          {isUp ? "UP" : "DOWN"}
        </p>
        {iface.ip_address && (
          <p className="font-mono text-xs text-gray-600 dark:text-gray-300">{iface.ip_address}</p>
        )}
        {media && (
          <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">{media}</p>
        )}
      </div>
    </div>
  );
}

// ── Dashboard page ────────────────────────────────────────────────────────────
export function DashboardPage({ navigate }: Props) {
  const { data, loading, error, refresh } = useDashboard();
  const { data: ifaceData, loading: ifaceLoading } = useFirewallInterfaces();
  const [runningSpeed, setRunningSpeed] = useState(false);

  async function handleRunSpeed() {
    setRunningSpeed(true);
    try {
      await api.triggerSpeedTest();
      await new Promise((r) => setTimeout(r, 2000));
      refresh();
    } catch { /* ignore */ } finally {
      setRunningSpeed(false);
    }
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 text-sm text-red-700 dark:text-red-400">
        {error}
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-gray-400 dark:text-gray-500">
        Loading dashboard…
      </div>
    );
  }

  const grade = data.latest_speed_test.grade;
  const interfaces = ifaceData?.interfaces ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Dashboard</h1>
        <button onClick={refresh} className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 underline">
          Refresh
        </button>
      </div>

      {/* ── Device counts ── */}
      <div>
        {/* "Devices" heading — the colour reference for stat labels */}
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Devices
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <ClickableStat label="Total"     value={data.devices.total}     onClick={() => navigate("devices", null)} />
          <ClickableStat label="Online"    value={data.devices.online}    onClick={() => navigate("devices", "online")}
            valueColor="text-green-600 dark:text-green-400" />
          <ClickableStat label="Offline"   value={data.devices.offline}   onClick={() => navigate("devices", "offline")}
            valueColor={data.devices.offline > 0 ? "text-red-600 dark:text-red-400" : "text-gray-800 dark:text-gray-100"} />
          <ClickableStat label="New today" value={data.devices.new_today} onClick={() => navigate("devices", "new_today")} />
        </div>
      </div>

      {/* ── Internet Speed + Firewall Interfaces (side by side, equal width) ── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

        {/* Internet Speed (half width) */}
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Internet Speed
            </h2>
            <button
              onClick={handleRunSpeed}
              disabled={runningSpeed}
              className="rounded-md bg-blue-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-40"
            >
              {runningSpeed ? "Running…" : "Run Test"}
            </button>
          </div>
          {data.latest_speed_test.download_mbps !== null ? (
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-2.5">
                <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wide">Download</p>
                <p className={`text-lg font-bold mt-0.5 ${grade ? gradeColors[grade] : "text-gray-800 dark:text-gray-100"}`}>
                  {data.latest_speed_test.download_mbps?.toFixed(0)}
                  <span className="text-[10px] font-normal ml-0.5 opacity-60">Mbps</span>
                </p>
              </div>
              <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-2.5">
                <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wide">Upload</p>
                <p className="text-lg font-bold mt-0.5 text-gray-700 dark:text-gray-300">
                  {data.latest_speed_test.upload_mbps?.toFixed(0)}
                  <span className="text-[10px] font-normal ml-0.5 opacity-60">Mbps</span>
                </p>
              </div>
              <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-2.5">
                <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wide">Ping</p>
                <p className={`text-lg font-bold mt-0.5 ${grade ? gradeColors[grade] : "text-gray-800 dark:text-gray-100"}`}>
                  {data.latest_speed_test.ping_ms?.toFixed(0)}
                  <span className="text-[10px] font-normal ml-0.5 opacity-60">ms</span>
                </p>
                {grade && <p className="text-[9px] mt-0.5 opacity-50 capitalize">{grade}</p>}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-4">No tests yet</p>
          )}
          {data.latest_speed_test.tested_at && (
            <p className="mt-2 text-[10px] text-gray-400 dark:text-gray-500">
              {data.latest_speed_test.server && `${data.latest_speed_test.server} · `}
              {formatDate(data.latest_speed_test.tested_at)}
            </p>
          )}
        </div>

        {/* Firewall Interfaces (half width) */}
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Firewall Interfaces
            </h2>
            {ifaceData?.source === "unavailable" && (
              <span className="text-[10px] text-gray-400 dark:text-gray-500">pfSense unavailable</span>
            )}
            {ifaceData?.source === "pfsense" && interfaces.length > 0 && (
              <span className="text-[10px] text-gray-400 dark:text-gray-500">
                {interfaces.filter(i => i.up).length}/{interfaces.length} up
              </span>
            )}
          </div>
          {ifaceLoading ? (
            <div className="py-6 text-center text-xs text-gray-400 dark:text-gray-500">Loading…</div>
          ) : interfaces.length === 0 ? (
            <div className="py-6 text-center text-xs text-gray-400 dark:text-gray-500">
              {ifaceData?.source === "pfsense" ? "No interfaces found" : "pfSense SSH not configured"}
            </div>
          ) : (
            <div>
              {interfaces.map((iface) => (
                <IfaceCard key={iface.name} iface={iface} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Last Scan + AdGuard ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">Last Scan</h2>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-3">
              <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wide">Found</p>
              <p className="text-xl font-bold text-gray-800 dark:text-gray-100 mt-0.5">
                {data.last_scan.last_scan_devices ?? "—"}
              </p>
            </div>
            <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-3">
              <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wide">When</p>
              <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mt-0.5 leading-tight">
                {formatDate(data.last_scan.last_scan_at) ?? "Never"}
              </p>
            </div>
          </div>
        </div>

        {data.adguard.total_queries !== null && (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">AdGuard DNS</h2>
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-3">
                <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wide">Queries</p>
                <p className="text-xl font-bold text-gray-800 dark:text-gray-100 mt-0.5">
                  {data.adguard.total_queries?.toLocaleString()}
                </p>
              </div>
              <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-3">
                <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wide">Blocked</p>
                <p className="text-xl font-bold text-green-600 dark:text-green-400 mt-0.5">
                  {data.adguard.block_rate_pct?.toFixed(1)}
                  <span className="text-xs font-normal ml-0.5 opacity-60">%</span>
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Speed chart ── */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-3">Speed History</h2>
        <SpeedChart />
      </div>

      {/* ── Recent Events ── */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">Recent Events</h2>
        <EventFeed events={data.recent_events} />
      </div>

      {/* ── Notifications ── */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">Notifications</h2>
        <div className="flex gap-4 text-sm">
          <div className="flex items-center gap-1.5">
            <div className={`h-2 w-2 rounded-full ${data.notifications.ntfy_enabled ? "bg-green-500" : "bg-gray-300"}`} />
            <span className="text-gray-600 dark:text-gray-400">ntfy</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className={`h-2 w-2 rounded-full ${data.notifications.telegram_enabled ? "bg-green-500" : "bg-gray-300"}`} />
            <span className="text-gray-600 dark:text-gray-400">Telegram</span>
          </div>
        </div>
      </div>
    </div>
  );
}
