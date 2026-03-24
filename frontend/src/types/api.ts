// NetSentry API types — mirrors netsentry/api/v1/devices.py schemas

export interface Device {
  mac_address: string;
  friendly_name: string | null;
  category: string | null;
  subcategory: string | null;
  owner: string | null;
  notes: string | null;
  vendor: string | null;
  device_type: string | null;
  os_family: string | null;
  os_version: string | null;
  current_ip: string | null;
  hostname: string | null;
  lifecycle: "active" | "historic" | "deleted";
  connection_type: string | null;
  is_online: boolean;
  is_monitored: boolean;
  first_seen: string;
  last_seen: string;
}

export interface IpHistoryEntry {
  ip_address: string;
  source: string;
  first_seen: string;
  last_seen: string;
}

export interface EventEntry {
  id: number;
  event_type: string;
  severity: string;
  timestamp: string;
  details: string;
}

export interface DeviceDetail extends Device {
  ip_history: IpHistoryEntry[];
  recent_events: EventEntry[];
}

export interface ScanStatus {
  is_scanning: boolean;
  last_scan: {
    id: number;
    scan_type: string;
    profile: string | null;
    started_at: string;
    completed_at: string | null;
    devices_found: number | null;
  } | null;
}

export interface HealthResponse {
  status: string;
  version: string;
}
