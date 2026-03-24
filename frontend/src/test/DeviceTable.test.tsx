import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DeviceTable } from "@/components/DeviceTable";
import type { Device } from "@/types/api";

const makeDevice = (overrides: Partial<Device> = {}): Device => ({
  mac_address: "aa:bb:cc:dd:ee:ff",
  friendly_name: null,
  category: null,
  subcategory: null,
  owner: null,
  notes: null,
  vendor: "Apple Inc.",
  device_type: null,
  os_family: null,
  os_version: null,
  netbios_name: null,
  ssdp_device_type: null,
  open_ports: [],
  services: [],
  mdns_services: [],
  last_port_scan: null,
  last_os_scan: null,
  current_ip: "192.168.1.10",
  hostname: "my-macbook",
  lifecycle: "active",
  connection_type: null,
  is_online: true,
  is_monitored: false,
  first_seen: "2026-01-01T00:00:00",
  last_seen: "2026-03-21T10:00:00",
  ...overrides,
});

describe("DeviceTable", () => {
  it("renders device rows", () => {
    const devices = [
      makeDevice({ friendly_name: "Device One" }),
      makeDevice({ mac_address: "11:22:33:44:55:66", friendly_name: "Device Two" }),
    ];
    const { container } = render(<DeviceTable devices={devices} loading={false} error={null} />);
    expect(container.textContent).toContain("Device One");
    expect(container.textContent).toContain("Device Two");
    expect(screen.getAllByText("Apple Inc.").length).toBeGreaterThan(0);
  });

  it("shows online badge for online device", () => {
    render(<DeviceTable devices={[makeDevice({ is_online: true })]} loading={false} error={null} />);
    expect(screen.getAllByText("Online").length).toBeGreaterThan(0);
  });

  it("shows offline badge for offline device", () => {
    render(<DeviceTable devices={[makeDevice({ is_online: false })]} loading={false} error={null} />);
    expect(screen.getAllByText("Offline").length).toBeGreaterThan(0);
  });

  it("shows friendly_name over hostname when set", () => {
    const device = makeDevice({ friendly_name: "Ian's MacBook", hostname: "macbook-local" });
    render(<DeviceTable devices={[device]} loading={false} error={null} />);
    expect(screen.getByText("Ian's MacBook")).toBeInTheDocument();
    expect(screen.queryByText("macbook-local")).not.toBeInTheDocument();
  });

  it("falls back to hostname when no friendly_name", () => {
    const device = makeDevice({ friendly_name: null, hostname: "macbook-local" });
    render(<DeviceTable devices={[device]} loading={false} error={null} />);
    expect(screen.getByText("macbook-local")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    render(<DeviceTable devices={[]} loading={true} error={null} />);
    expect(screen.getByText(/loading devices/i)).toBeInTheDocument();
  });

  it("shows empty state when no devices", () => {
    render(<DeviceTable devices={[]} loading={false} error={null} />);
    expect(screen.getByText(/no devices found/i)).toBeInTheDocument();
  });

  it("shows error state with retry button", () => {
    render(<DeviceTable devices={[]} loading={false} error="Connection refused" />);
    expect(screen.getByText(/connection refused/i)).toBeInTheDocument();
    expect(screen.getByText(/retry/i)).toBeInTheDocument();
  });

  it("shows vendor column", () => {
    render(<DeviceTable devices={[makeDevice()]} loading={false} error={null} />);
    expect(screen.getAllByText("Apple Inc.").length).toBeGreaterThan(0);
  });

  it("shows IP address column", () => {
    render(<DeviceTable devices={[makeDevice()]} loading={false} error={null} />);
    expect(screen.getByText("192.168.1.10")).toBeInTheDocument();
  });
});
