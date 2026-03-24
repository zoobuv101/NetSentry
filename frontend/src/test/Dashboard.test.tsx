import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard } from "@/components/StatCard";
import { EventFeed } from "@/components/EventFeed";

describe("StatCard", () => {
  it("renders label and value", () => {
    render(<StatCard label="Online" value={42} />);
    expect(screen.getByText("Online")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders sub text when provided", () => {
    render(<StatCard label="Speed" value="95 Mbps" sub="excellent" />);
    expect(screen.getByText("excellent")).toBeInTheDocument();
  });

  it("renders dash for null value", () => {
    render(<StatCard label="Speed" value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("EventFeed", () => {
  it("renders empty state when no events", () => {
    render(<EventFeed events={[]} />);
    expect(screen.getByText(/no recent events/i)).toBeInTheDocument();
  });

  it("renders event type labels", () => {
    const events = [
      { id: 1, event_type: "device.new", severity: "urgent", mac_address: "aa:bb:cc:dd:ee:ff", hostname: "my-phone", ip_address: "192.168.1.10", details: {}, timestamp: "2026-01-01T10:00:00" },
      { id: 2, event_type: "device.offline", severity: "high", mac_address: "11:22:33:44:55:66", hostname: null, ip_address: null, details: {}, timestamp: "2026-01-01T09:00:00" },
    ];
    render(<EventFeed events={events} />);
    expect(screen.getByText("New device")).toBeInTheDocument();
    expect(screen.getByText("Went offline")).toBeInTheDocument();
  });

  it("renders MAC addresses", () => {
    const events = [
      { id: 1, event_type: "device.new", severity: "info", mac_address: "aa:bb:cc:dd:ee:ff", hostname: "my-phone", ip_address: "192.168.1.10", details: {}, timestamp: "2026-01-01T10:00:00" },
    ];
    render(<EventFeed events={events} />);
    expect(screen.getByText("aa:bb:cc:dd:ee:ff")).toBeInTheDocument();
  });

  it("handles null mac_address gracefully", () => {
    const events = [
      { id: 1, event_type: "system.startup", severity: "info", mac_address: null, hostname: null, ip_address: null, details: {}, timestamp: "2026-01-01T10:00:00" },
    ];
    render(<EventFeed events={events} />);
    expect(screen.queryByText("null")).not.toBeInTheDocument();
  });
});
