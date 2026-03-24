import { useDashboard } from "@/hooks/useDashboard";
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

interface ClickableStatProps {
  label: string;
  value: string | number | null;
  sub?: string;
  onClick?: () => void;
  highlight?: "blue" | "green" | "red" | "gray";
}

function ClickableStat({ label, value, sub, onClick, highlight = "gray" }: ClickableStatProps) {
  const base = "rounded-lg border p-4 transition-all";
  const colors: Record<string, string> = {
    blue:  "bg-blue-50  border-blue-200  dark:bg-blue-900/20  dark:border-blue-800",
    green: "bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800",
    red:   "bg-red-50   border-red-200   dark:bg-red-900/20   dark:border-red-800",
    gray:  "bg-gray-50  border-gray-200  dark:bg-gray-800     dark:border-gray-700",
  };
  const textColors: Record<string, string> = {
    blue:  "text-blue-700  dark:text-blue-400",
    green: "text-green-700 dark:text-green-400",
    red:   "text-red-700   dark:text-red-400",
    gray:  "text-gray-700  dark:text-gray-300",
  };
  const clickable = onClick
    ? "cursor-pointer hover:shadow-md hover:scale-[1.02] hover:ring-2 ring-blue-400/40"
    : "";

  return (
    <div className={`${base} ${colors[highlight]} ${clickable}`} onClick={onClick} role={onClick ? "button" : undefined}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-60">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${textColors[highlight]}`}>
        {value ?? <span className="text-base font-normal opacity-40">—</span>}
      </p>
      {sub && <p className="mt-0.5 text-xs opacity-60">{sub}</p>}
      {onClick && (
        <p className="mt-1.5 text-[10px] opacity-50 font-medium tracking-wide">
          VIEW DEVICES →
        </p>
      )}
    </div>
  );
}

export function DashboardPage({ navigate }: Props) {
  const { data, loading, error, refresh } = useDashboard();
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Dashboard</h1>
        <button onClick={refresh} className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 underline">
          Refresh
        </button>
      </div>

      {/* Device counts — all clickable */}
      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Devices
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <ClickableStat
            label="Total"
            value={data.devices.total}
            highlight="blue"
            onClick={() => navigate("devices", null)}
          />
          <ClickableStat
            label="Online"
            value={data.devices.online}
            highlight="green"
            onClick={() => navigate("devices", "online")}
          />
          <ClickableStat
            label="Offline"
            value={data.devices.offline}
            highlight={data.devices.offline > 0 ? "red" : "gray"}
            onClick={() => navigate("devices", "offline")}
          />
          <ClickableStat
            label="New today"
            value={data.devices.new_today}
            highlight="blue"
            onClick={() => navigate("devices", "new_today")}
          />
        </div>
      </div>

      {/* Speed + last scan */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Internet Speed</h2>
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
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-3">
                <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Download</p>
                <p className={`text-xl font-bold mt-0.5 ${grade ? gradeColors[grade] : ""}`}>
                  {data.latest_speed_test.download_mbps?.toFixed(1)}
                  <span className="text-xs font-normal ml-0.5 opacity-60">Mbps</span>
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-3">
                <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Upload</p>
                <p className="text-xl font-bold mt-0.5 text-gray-700 dark:text-gray-300">
                  {data.latest_speed_test.upload_mbps?.toFixed(1)}
                  <span className="text-xs font-normal ml-0.5 opacity-60">Mbps</span>
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-3">
                <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Ping</p>
                <p className={`text-xl font-bold mt-0.5 ${grade ? gradeColors[grade] : ""}`}>
                  {data.latest_speed_test.ping_ms?.toFixed(0)}
                  <span className="text-xs font-normal ml-0.5 opacity-60">ms</span>
                </p>
                {grade && <p className="text-[10px] mt-0.5 opacity-50 capitalize">{grade}</p>}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-4">No tests yet</p>
          )}
          {data.latest_speed_test.tested_at && (
            <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
              Last tested {formatDate(data.latest_speed_test.tested_at)}
            </p>
          )}
        </div>

        <div className="space-y-3">
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Last Scan</h2>
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-3">
                <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Found</p>
                <p className="text-xl font-bold text-blue-700 dark:text-blue-400 mt-0.5">
                  {data.last_scan.last_scan_devices ?? "—"}
                </p>
              </div>
              <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-3">
                <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">When</p>
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mt-0.5 leading-tight">
                  {formatDate(data.last_scan.last_scan_at) ?? "Never"}
                </p>
              </div>
            </div>
          </div>

          {data.adguard.total_queries !== null && (
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">AdGuard DNS</h2>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-3">
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Queries</p>
                  <p className="text-xl font-bold text-blue-700 dark:text-blue-400 mt-0.5">
                    {data.adguard.total_queries?.toLocaleString()}
                  </p>
                </div>
                <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-3">
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Blocked</p>
                  <p className="text-xl font-bold text-green-700 dark:text-green-400 mt-0.5">
                    {data.adguard.block_rate_pct?.toFixed(1)}
                    <span className="text-xs font-normal ml-0.5 opacity-60">%</span>
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Speed chart */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Speed History</h2>
        <SpeedChart />
      </div>

      {/* Events */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Recent Events</h2>
        <EventFeed events={data.recent_events} />
      </div>

      {/* Notification status */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Notifications</h2>
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
