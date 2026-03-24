interface Event {
  id: number;
  event_type: string;
  severity: string;
  mac_address: string | null;
  timestamp: string;
}

const severityStyles: Record<string, string> = {
  urgent:  "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  high:    "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  info:    "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400",
  default: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

const eventLabels: Record<string, string> = {
  "device.new":         "New device",
  "device.offline":     "Device offline",
  "device.online":      "Device online",
  "availability.down":  "Unreachable",
  "availability.up":    "Reachable",
  "deco.device_roamed": "Roamed",
};

function formatTime(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(new Date(iso));
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
        <li key={ev.id} className="flex items-center gap-3 py-2.5">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${severityStyles[ev.severity] ?? severityStyles.default}`}>
            {eventLabels[ev.event_type] ?? ev.event_type}
          </span>
          {ev.mac_address && (
            <span className="font-mono text-xs text-gray-500 dark:text-gray-400 truncate">
              {ev.mac_address}
            </span>
          )}
          <span className="ml-auto text-xs text-gray-400 dark:text-gray-500 shrink-0">
            {formatTime(ev.timestamp)}
          </span>
        </li>
      ))}
    </ul>
  );
}
