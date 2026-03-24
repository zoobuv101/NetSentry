interface Event {
  id: number;
  event_type: string;
  severity: string;
  mac_address: string | null;
  timestamp: string;
}

const severityStyles: Record<string, string> = {
  urgent:  "bg-red-100 text-red-700",
  high:    "bg-orange-100 text-orange-700",
  info:    "bg-blue-100 text-blue-600",
  default: "bg-gray-100 text-gray-600",
};

const eventLabels: Record<string, string> = {
  "device.new":           "New device",
  "device.offline":       "Device offline",
  "device.online":        "Device online",
  "availability.down":    "Unreachable",
  "availability.up":      "Reachable",
  "deco.device_roamed":   "Roamed",
};

function formatTime(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

interface Props {
  events: Event[];
}

export function EventFeed({ events }: Props) {
  if (events.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-gray-400">
        No recent events
      </div>
    );
  }

  return (
    <ul className="divide-y divide-gray-100">
      {events.map((ev) => (
        <li key={ev.id} className="flex items-center gap-3 py-2.5">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              severityStyles[ev.severity] ?? severityStyles.default
            }`}
          >
            {eventLabels[ev.event_type] ?? ev.event_type}
          </span>
          {ev.mac_address && (
            <span className="font-mono text-xs text-gray-500 truncate">
              {ev.mac_address}
            </span>
          )}
          <span className="ml-auto text-xs text-gray-400 shrink-0">
            {formatTime(ev.timestamp)}
          </span>
        </li>
      ))}
    </ul>
  );
}
