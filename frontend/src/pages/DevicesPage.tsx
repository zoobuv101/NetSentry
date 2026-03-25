import { useState, useEffect } from "react";
import { useDevices } from "@/hooks/useDevices";
import { DeviceTable } from "@/components/DeviceTable";
import { api } from "@/api/client";
import type { DeviceFilter } from "@/App";

interface Props {
  initialFilter?: DeviceFilter;
}

export function DevicesPage({ initialFilter = null }: Props) {
  const { devices, loading, error, refresh, lifecycle, setLifecycle } = useDevices();

  // Track active filter as state so prop changes from dashboard deep-links
  // are picked up even when this page is already mounted
  const [activeFilter, setActiveFilter] = useState<DeviceFilter>(initialFilter);
  useEffect(() => {
    setActiveFilter(initialFilter);
  }, [initialFilter]);

  async function handleScan() {
    try {
      await api.triggerScan("quick");
      setTimeout(refresh, 3000);
    } catch {
      // scan trigger failed — ignore silently
    }
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Devices
            {!loading && (
              <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">
                ({devices.length})
              </span>
            )}
          </h1>
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={lifecycle === "historic"}
              onChange={(e) => setLifecycle(e.target.checked ? "historic" : "active")}
              className="rounded border-gray-300 dark:border-gray-600"
            />
            Show historic
          </label>
        </div>
        <button
          onClick={handleScan}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Scan Now
        </button>
      </div>

      <DeviceTable
        devices={devices}
        loading={loading}
        error={error}
        initialStatus={activeFilter}
      />
    </div>
  );
}
