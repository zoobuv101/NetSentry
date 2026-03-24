import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { Device } from "@/types/api";

interface UseDevicesResult {
  devices: Device[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
  lifecycle: string;
  setLifecycle: (lc: string) => void;
}

const POLL_INTERVAL_MS = 10_000;

export function useDevices(): UseDevicesResult {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lifecycle, setLifecycle] = useState("active");

  const fetch = useCallback(async () => {
    try {
      const data = await api.getDevices(lifecycle);
      setDevices(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [lifecycle]);

  useEffect(() => {
    setLoading(true);
    fetch();
    const id = setInterval(fetch, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetch]);

  return { devices, loading, error, refresh: fetch, lifecycle, setLifecycle };
}
