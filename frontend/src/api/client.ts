// NetSentry API client
import type { Device, DeviceDetail, ScanStatus, HealthResponse } from "@/types/api";

const BASE = "/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.message ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Devices
  getDevices: (lifecycle = "active") =>
    apiFetch<Device[]>(`/devices?lifecycle=${lifecycle}`),

  getDevice: (mac: string) =>
    apiFetch<DeviceDetail>(`/devices/${encodeURIComponent(mac)}`),

  // Scan
  triggerScan: (profile = "standard") =>
    apiFetch<{ accepted: boolean; profile: string; message: string }>(
      "/scan/trigger",
      { method: "POST", body: JSON.stringify({ profile }) }
    ),

  getScanStatus: () => apiFetch<ScanStatus>("/scan/status"),

  // System
  getHealth: () => apiFetch<HealthResponse>("/system/health"),
};
