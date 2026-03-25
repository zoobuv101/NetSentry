// NetSentry API client
import type { Device, DeviceDetail, ScanStatus, HealthResponse, EventLogResponse } from "@/types/api";

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

  patchDevice: (mac: string, body: { alerts_enabled?: boolean; friendly_name?: string; notes?: string }) =>
    apiFetch<Device>(`/devices/${encodeURIComponent(mac)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  // Events log
  getEvents: (params: { q?: string; event_type?: string; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.q)          qs.set("q", params.q);
    if (params.event_type) qs.set("event_type", params.event_type);
    if (params.limit)      qs.set("limit", String(params.limit));
    if (params.offset)     qs.set("offset", String(params.offset));
    const query = qs.toString();
    return apiFetch<EventLogResponse>(`/events${query ? "?" + query : ""}`);
  },

  // Scan
  triggerScan: (profile = "standard") =>
    apiFetch<{ accepted: boolean; profile: string; message: string }>(
      "/scan/trigger",
      { method: "POST", body: JSON.stringify({ profile }) }
    ),

  getScanStatus: () => apiFetch<ScanStatus>("/scan/status"),

  // System
  getHealth: () => apiFetch<HealthResponse>("/system/health"),

  // Dashboard
  getDashboardSummary: () =>
    apiFetch<unknown>("/dashboard/summary"),

  // Speed test
  getSpeedTestHistory: () =>
    apiFetch<{ results: unknown[]; count: number }>("/speedtest/history"),

  triggerSpeedTest: () =>
    apiFetch<unknown>("/speedtest/run", { method: "POST" }),
};
