import type { Device } from "@/types/api";

interface Props {
  devices: Device[];
  loading: boolean;
  error: string | null;
}

function statusBadge(online: boolean) {
  return online ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
      <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
      Online
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
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

export function DeviceTable({ devices, loading, error }: Props) {
  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <strong>Error loading devices:</strong> {error}
        <button
          className="ml-3 underline hover:no-underline"
          onClick={() => window.location.reload()}
        >
          Retry
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-gray-500">
        Loading devices…
      </div>
    );
  }

  if (devices.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-gray-500">
        No devices found. Waiting for first scan…
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            {["Name", "IP Address", "MAC", "Vendor", "Status", "Last Seen"].map(
              (col) => (
                <th
                  key={col}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  {col}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {devices.map((device) => (
            <tr
              key={device.mac_address}
              className="hover:bg-gray-50 transition-colors"
            >
              <td className="px-4 py-3 font-medium text-gray-900">
                {device.friendly_name ?? device.hostname ?? device.mac_address}
              </td>
              <td className="px-4 py-3 font-mono text-gray-700">
                {device.current_ip ?? "—"}
              </td>
              <td className="px-4 py-3 font-mono text-gray-500 text-xs">
                {device.mac_address}
              </td>
              <td className="px-4 py-3 text-gray-600">
                {device.vendor ?? "—"}
              </td>
              <td className="px-4 py-3">{statusBadge(device.is_online)}</td>
              <td className="px-4 py-3 text-gray-500">
                {formatDate(device.last_seen)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
