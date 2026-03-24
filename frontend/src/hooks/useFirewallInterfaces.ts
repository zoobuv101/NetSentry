import { useState, useEffect, useCallback } from "react";

export interface InterfaceStatus {
  name: string;
  description: string | null;
  up: boolean;
  running: boolean;
  ip_address: string | null;
  ip6_address: string | null;
  media: string | null;
  flags: string[];
}

export interface InterfacesData {
  interfaces: InterfaceStatus[];
  source: string;
}

export function useFirewallInterfaces() {
  const [data, setData] = useState<InterfacesData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const res = await window.fetch("/api/v1/pfsense/interfaces");
      if (res.ok) {
        setData(await res.json());
      }
    } catch {
      // silently ignore — pfSense may not be configured
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    const id = setInterval(fetch, 30_000);
    return () => clearInterval(id);
  }, [fetch]);

  return { data, loading, refresh: fetch };
}
