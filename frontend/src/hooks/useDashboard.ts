import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";

export interface DashboardData {
  devices: {
    total: number;
    online: number;
    offline: number;
    new_today: number;
  };
  last_scan: {
    last_scan_at: string | null;
    last_scan_devices: number | null;
    is_scanning: boolean;
  };
  latest_speed_test: {
    download_mbps: number | null;
    upload_mbps: number | null;
    ping_ms: number | null;
    grade: string | null;
    tested_at: string | null;
  };
  notifications: {
    ntfy_enabled: boolean;
    telegram_enabled: boolean;
  };
  adguard: {
    total_queries: number | null;
    blocked_queries: number | null;
    block_rate_pct: number | null;
  };
  recent_events: Array<{
    id: number;
    event_type: string;
    severity: string;
    mac_address: string | null;
    timestamp: string;
  }>;
}

export function useDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      const result = await api.getDashboardSummary();
      setData(result as DashboardData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    const id = setInterval(fetch, 30_000);
    return () => clearInterval(id);
  }, [fetch]);

  return { data, loading, error, refresh: fetch };
}
