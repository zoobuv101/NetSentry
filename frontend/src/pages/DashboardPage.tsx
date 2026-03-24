import { Responsive, WidthProvider } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { useDashboard } from "@/hooks/useDashboard";
import { useFirewallInterfaces } from "@/hooks/useFirewallInterfaces";
import { useDashboardLayout } from "@/hooks/useDashboardLayout";
import type { InterfaceStatus } from "@/hooks/useFirewallInterfaces";
import { SpeedChart } from "@/components/SpeedChart";
import { EventFeed } from "@/components/EventFeed";
import { api } from "@/api/client";
import { useState } from "react";
import type { Page, DeviceFilter } from "@/App";

const ResponsiveGrid = WidthProvider(Responsive);

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

// ── Widget shell ──────────────────────────────────────────────────────────────
function Widget({ title, children, editMode, action }: {
  title: string;
  children: React.ReactNode;
  editMode: boolean;
  action?: React.ReactNode;
}) {
  return (
    <div className={`h-full flex flex-col rounded-lg border bg-white dark:bg-gray-900 overflow-hidden
      ${editMode
        ? "border-blue-300 dark:border-blue-700 shadow-md cursor-grab active:cursor-grabbing"
        : "border-gray-200 dark:border-gray-700"
      }`}>
      <div className={`flex items-center justify-between px-4 py-2.5 border-b
        ${editMode ? "border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/20" : "border-gray-100 dark:border-gray-800"}`}>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 select-none">
          {editMode && <span className="mr-1.5 opacity-40">⠿</span>}
          {title}
        </h2>
        {action}
      </div>
      <div className="flex-1 overflow-auto p-4">
        {children}
      </div>
    </div>
  );
}

// ── Clickable stat ────────────────────────────────────────────────────────────
function ClickableStat({ label, value, onClick, valueColor = "text-gray-800 dark:text-gray-100" }: {
  label: string; value: string | number | null; onClick?: () => void; valueColor?: string;
}) {
  return (
    <div
      onClick={onClick}
      role={onClick ? "button" : undefined}
      className={`rounded-lg border border-gray-200 dark:border-gray-700 p-4
        ${onClick ? "cursor-pointer hover:shadow-md hover:scale-[1.02] hover:ring-2 ring-blue-400/30 transition-all" : ""}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${valueColor}`}>
        {value ?? <span className="text-base opacity-40">—</span>}
      </p>
      {onClick && <p className="mt-1 text-[10px] text-gray-400 font-medium tracking-wide">VIEW DEVICES →</p>}
    </div>
  );
}

// ── Firewall interface row ────────────────────────────────────────────────────
function IfaceRow({ iface }: { iface: InterfaceStatus }) {
  const label = iface.description || iface.name.toUpperCase();
  const isUp = iface.up && iface.running;
  const media = iface.media
    ? iface.media.replace("Ethernet ", "").replace(" <full-duplex>", " FD").replace(" <half-duplex>", " HD")
    : null;
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        <div className={`h-2 w-2 rounded-full shrink-0 ${isUp ? "bg-green-500" : "bg-red-400"}`} />
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">{label}</p>
          <p className="font-mono text-xs text-gray-400">{iface.name}</p>
        </div>
      </div>
      <div className="text-right shrink-0 ml-3">
        <p className={`text-xs font-semibold ${isUp ? "text-green-600 dark:text-green-400" : "text-red-500"}`}>
          {isUp ? "UP" : "DOWN"}
        </p>
        {iface.ip_address && <p className="font-mono text-xs text-gray-600 dark:text-gray-300">{iface.ip_address}</p>}
        {media && <p className="text-[10px] text-gray-400 mt-0.5">{media}</p>}
      </div>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export function DashboardPage({ navigate }: Props) {
  const { data, loading, error, refresh } = useDashboard();
  const { data: ifaceData, loading: ifaceLoading } = useFirewallInterfaces();
  const { layout, editMode, setEditMode, onLayoutChange, resetLayout } = useDashboardLayout();
  const [runningSpeed, setRunningSpeed] = useState(false);

  async function handleRunSpeed() {
    setRunningSpeed(true);
    try { await api.triggerSpeedTest(); await new Promise((r) => setTimeout(r, 2000)); refresh(); }
    catch { /* ignore */ } finally { setRunningSpeed(false); }
  }

  if (error) return (
    <div className="rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 text-sm text-red-700 dark:text-red-400">{error}</div>
  );

  if (loading || !data) return (
    <div className="flex items-center justify-center py-16 text-sm text-gray-400">Loading dashboard…</div>
  );

  const grade = data.latest_speed_test.grade;
  const interfaces = ifaceData?.interfaces ?? [];

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Dashboard</h1>
        <div className="flex items-center gap-2">
          {editMode && (
            <button onClick={resetLayout} className="text-xs text-gray-400 hover:text-gray-600 underline">
              Reset layout
            </button>
          )}
          <button
            onClick={() => setEditMode(!editMode)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              editMode
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
            }`}
          >
            {editMode ? "✓ Done editing" : "⠿ Edit layout"}
          </button>
          <button onClick={refresh} className="text-xs text-gray-500 hover:text-gray-700 underline">Refresh</button>
        </div>
      </div>

      {editMode && (
        <p className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 rounded px-3 py-2">
          Drag widgets to rearrange • Drag the bottom-right corner to resize • Layout is saved automatically
        </p>
      )}

      <ResponsiveGrid
        className="layout"
        layouts={{ lg: layout }}
        breakpoints={{ lg: 1200, md: 768, sm: 480 }}
        cols={{ lg: 12, md: 8, sm: 4 }}
        rowHeight={60}
        isDraggable={editMode}
        isResizable={editMode}
        onLayoutChange={(_, layouts) => onLayoutChange(layouts.lg ?? layout)}
        margin={[12, 12]}
        containerPadding={[0, 0]}
        draggableHandle=".drag-handle"
        resizeHandles={["se"]}
      >
        {/* ── Devices ── */}
        <div key="devices" className="drag-handle">
          <Widget title="Devices" editMode={editMode}>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <ClickableStat label="Total"     value={data.devices.total}     onClick={() => navigate("devices", null)} />
              <ClickableStat label="Online"    value={data.devices.online}    onClick={() => navigate("devices", "online")}
                valueColor="text-green-600 dark:text-green-400" />
              <ClickableStat label="Offline"   value={data.devices.offline}   onClick={() => navigate("devices", "offline")}
                valueColor={data.devices.offline > 0 ? "text-red-600 dark:text-red-400" : undefined} />
              <ClickableStat label="New today" value={data.devices.new_today} onClick={() => navigate("devices", "new_today")} />
            </div>
          </Widget>
        </div>

        {/* ── Internet Speed ── */}
        <div key="speed" className="drag-handle">
          <Widget title="Internet Speed" editMode={editMode}
            action={
              <button onClick={handleRunSpeed} disabled={runningSpeed}
                className="rounded bg-blue-600 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-blue-700 disabled:opacity-40">
                {runningSpeed ? "Running…" : "Run Test"}
              </button>
            }>
            {data.latest_speed_test.download_mbps !== null ? (
              <>
                <div className="grid grid-cols-3 gap-2 mb-2">
                  <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-2.5">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">Download</p>
                    <p className={`text-lg font-bold mt-0.5 ${grade ? gradeColors[grade] : ""}`}>
                      {data.latest_speed_test.download_mbps?.toFixed(0)}<span className="text-[10px] opacity-60 ml-0.5">Mbps</span>
                    </p>
                  </div>
                  <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-2.5">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">Upload</p>
                    <p className="text-lg font-bold mt-0.5 text-gray-700 dark:text-gray-300">
                      {data.latest_speed_test.upload_mbps?.toFixed(0)}<span className="text-[10px] opacity-60 ml-0.5">Mbps</span>
                    </p>
                  </div>
                  <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-2.5">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">Ping</p>
                    <p className={`text-lg font-bold mt-0.5 ${grade ? gradeColors[grade] : ""}`}>
                      {data.latest_speed_test.ping_ms?.toFixed(0)}<span className="text-[10px] opacity-60 ml-0.5">ms</span>
                    </p>
                    {grade && <p className="text-[9px] mt-0.5 opacity-50 capitalize">{grade}</p>}
                  </div>
                </div>
                {data.latest_speed_test.tested_at && (
                  <p className="text-[10px] text-gray-400">
                    {data.latest_speed_test.server && `${data.latest_speed_test.server} · `}
                    {formatDate(data.latest_speed_test.tested_at)}
                  </p>
                )}
              </>
            ) : (
              <p className="text-sm text-gray-400 text-center py-4">No tests yet</p>
            )}
          </Widget>
        </div>

        {/* ── Firewall Interfaces ── */}
        <div key="firewall" className="drag-handle">
          <Widget title="Firewall Interfaces" editMode={editMode}
            action={
              ifaceData?.source === "pfsense" && interfaces.length > 0
                ? <span className="text-[10px] text-gray-400">{interfaces.filter(i => i.up).length}/{interfaces.length} up</span>
                : <span className="text-[10px] text-gray-400">{ifaceData?.source === "unavailable" ? "unavailable" : ""}</span>
            }>
            {ifaceLoading ? (
              <p className="text-xs text-gray-400 text-center py-4">Loading…</p>
            ) : interfaces.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-4">
                {ifaceData?.source === "pfsense" ? "No interfaces" : "pfSense not configured"}
              </p>
            ) : (
              interfaces.map((iface) => <IfaceRow key={iface.name} iface={iface} />)
            )}
            {ifaceData?.last_updated && (
              <p className="text-[10px] text-gray-400 mt-2">Updated {formatDate(ifaceData.last_updated)}</p>
            )}
          </Widget>
        </div>

        {/* ── Last Scan + AdGuard ── */}
        <div key="scan_adguard" className="drag-handle">
          <Widget title="Scan & DNS" editMode={editMode}>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-3">
                <p className="text-[10px] text-gray-500 uppercase tracking-wide">Devices found</p>
                <p className="text-xl font-bold text-gray-800 dark:text-gray-100 mt-0.5">{data.last_scan.last_scan_devices ?? "—"}</p>
              </div>
              <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-3">
                <p className="text-[10px] text-gray-500 uppercase tracking-wide">Last scan</p>
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mt-0.5">{formatDate(data.last_scan.last_scan_at) ?? "Never"}</p>
              </div>
              {data.adguard.total_queries !== null && <>
                <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-3">
                  <p className="text-[10px] text-gray-500 uppercase tracking-wide">DNS queries</p>
                  <p className="text-xl font-bold text-gray-800 dark:text-gray-100 mt-0.5">{data.adguard.total_queries?.toLocaleString()}</p>
                </div>
                <div className="rounded bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-3">
                  <p className="text-[10px] text-gray-500 uppercase tracking-wide">Blocked</p>
                  <p className="text-xl font-bold text-green-600 dark:text-green-400 mt-0.5">
                    {data.adguard.block_rate_pct?.toFixed(1)}<span className="text-xs opacity-60 ml-0.5">%</span>
                  </p>
                </div>
              </>}
            </div>
          </Widget>
        </div>

        {/* ── Speed Chart ── */}
        <div key="speed_chart" className="drag-handle">
          <Widget title="Speed History" editMode={editMode}>
            <SpeedChart />
          </Widget>
        </div>

        {/* ── Events ── */}
        <div key="events" className="drag-handle">
          <Widget title="Recent Events" editMode={editMode}>
            <EventFeed events={data.recent_events} />
          </Widget>
        </div>

        {/* ── Notifications ── */}
        <div key="notifications" className="drag-handle">
          <Widget title="Notifications" editMode={editMode}>
            <div className="space-y-2">
              {[
                { label: "ntfy", enabled: data.notifications.ntfy_enabled },
                { label: "Telegram", enabled: data.notifications.telegram_enabled },
              ].map(({ label, enabled }) => (
                <div key={label} className="flex items-center gap-2">
                  <div className={`h-2 w-2 rounded-full ${enabled ? "bg-green-500" : "bg-gray-300"}`} />
                  <span className="text-sm text-gray-600 dark:text-gray-400">{label}</span>
                  <span className={`ml-auto text-xs ${enabled ? "text-green-600 dark:text-green-400" : "text-gray-400"}`}>
                    {enabled ? "Active" : "Disabled"}
                  </span>
                </div>
              ))}
            </div>
          </Widget>
        </div>
      </ResponsiveGrid>
    </div>
  );
}
