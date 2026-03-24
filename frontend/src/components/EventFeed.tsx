interface Event {
  id: number;
  event_type: string;
  severity: string;
  mac_address: string | null;
  hostname: string | null;
  ip_address: string | null;
  details: Record<string, unknown>;
  timestamp: string;
}

const severityStyles: Record<string, string> = {
  urgent:  "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  high:    "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  info:    "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400",
  default: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

const eventLabels: Record<string, string> = {
  "device.new":           "New device",
  "device.offline":       "Went offline",
  "device.online":        "Came online",
  "availability.down":    "Unreachable",
  "availability.up":      "Reachable",
  "deco.device_roamed":   "Roamed",
};

function formatTime(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    }).format(new Date(iso));
  } catch { return iso; }
}

export function EventFeed({ events }: { events: Event[] }) {
  if (events.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">
        No recent events
      </div>
    );
  }

  return (
    <ul className="divide-y divide-gray-100 dark:divide-gray-800">
      {events.map((ev) => (
        <li key={ev.id} className="py-3 flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium shrink-0 ${
              severityStyles[ev.severity] ?? severityStyles.default
            }`}>
              {eventLabels[ev.event_type] ?? ev.event_type}
            </span>
            {/* Device name — prefer hostname, fall back to MAC */}
            <span className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
              {ev.hostname ?? ev.mac_address ?? "Unknown"}
            </span>
            <span className="ml-auto text-xs text-gray-400 dark:text-gray-500 shrink-0">
              {formatTime(ev.timestamp)}
            </span>
          </div>
          {/* IP address and MAC on second line */}
          <div className="flex items-center gap-3 pl-1">
            {ev.ip_address && (
              <span className="font-mono text-xs text-gray-500 dark:text-gray-400">
                {ev.ip_address}
              </span>
            )}
            {ev.mac_address && (
              <span className="font-mono text-xs text-gray-400 dark:text-gray-500">
                {ev.mac_address}
              </span>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
