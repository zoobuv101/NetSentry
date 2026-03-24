import { useDashboard } from "@/hooks/useDashboard";
import { StatCard } from "@/components/StatCard";
import { SpeedChart } from "@/components/SpeedChart";
import { EventFeed } from "@/components/EventFeed";
import { api } from "@/api/client";
import { useState } from "react";

const gradeColors: Record<string, "green" | "yellow" | "red" | "gray"> = {
  excellent: "green",
  good: "green",
  fair: "yellow",
  poor: "red",
};

function formatDate(iso: string | null) {
  if (!iso) return null;
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function DashboardPage() {
  const { data, loading, error, refresh } = useDashboard();
  const [runningSpeed, setRunningSpeed] = useState(false);

  async function handleRunSpeed() {
    setRunningSpeed(true);
    try {
      await api.triggerSpeedTest();
      await new Promise((r) => setTimeout(r, 2000));
      refresh();
    } catch {
      // silently ignore
    } finally {
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
        <button
          onClick={refresh}
          className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 underline"
        >
          Refresh
        </button>
      </div>

      {/* Device counts */}
      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Devices
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Total" value={data.devices.total} color="blue" />
          <StatCard label="Online" value={data.devices.online} color="green" />
          <StatCard label="Offline" value={data.devices.offline} color={data.devices.offline > 0 ? "red" : "gray"} />
          <StatCard label="New today" value={data.devices.new_today} color="blue" />
        </div>
      </div>

      {/* Speed + last scan */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Speed */}
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
              <StatCard
                label="Download"
                value={`${data.latest_speed_test.download_mbps?.toFixed(1)} Mbps`}
                color={gradeColors[grade ?? ""] ?? "gray"}
              />
              <StatCard
                label="Upload"
                value={`${data.latest_speed_test.upload_mbps?.toFixed(1)} Mbps`}
                color="gray"
              />
              <StatCard
                label="Ping"
                value={`${data.latest_speed_test.ping_ms?.toFixed(0)} ms`}
                sub={grade ?? undefined}
                color={gradeColors[grade ?? ""] ?? "gray"}
              />
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

        {/* Last scan + AdGuard */}
        <div className="space-y-3">
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Last Scan</h2>
            <div className="grid grid-cols-2 gap-2">
              <StatCard
                label="Devices found"
                value={data.last_scan.last_scan_devices ?? "—"}
                color="blue"
              />
              <StatCard
                label="Scanned at"
                value={formatDate(data.last_scan.last_scan_at) ?? "Never"}
                color="gray"
              />
            </div>
          </div>

          {data.adguard.total_queries !== null && (
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">AdGuard DNS</h2>
              <div className="grid grid-cols-2 gap-2">
                <StatCard label="Queries" value={data.adguard.total_queries?.toLocaleString() ?? "—"} color="blue" />
                <StatCard
                  label="Blocked"
                  value={`${data.adguard.block_rate_pct?.toFixed(1)}%`}
                  sub={`${data.adguard.blocked_queries?.toLocaleString()} blocked`}
                  color="green"
                />
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

      {/* Recent events */}
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
            <span className="text-gray-600">ntfy</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className={`h-2 w-2 rounded-full ${data.notifications.telegram_enabled ? "bg-green-500" : "bg-gray-300"}`} />
            <span className="text-gray-600">Telegram</span>
          </div>
        </div>
      </div>
    </div>
  );
}
