import { useState, useCallback } from "react";
import type { Layout } from "react-grid-layout";

export type WidgetId =
  | "devices"
  | "speed"
  | "firewall"
  | "scan_adguard"
  | "speed_chart"
  | "events"
  | "notifications";

const STORAGE_KEY = "netsentry-dashboard-layout";

// Default layout — 12-column grid, each unit ≈ 1/12 of width
// x, y, w, h — h units are ~80px each
export const DEFAULT_LAYOUT: Layout[] = [
  { i: "devices",       x: 0,  y: 0,  w: 12, h: 4, minW: 6,  minH: 3 },
  { i: "speed",         x: 0,  y: 4,  w: 6,  h: 5, minW: 4,  minH: 4 },
  { i: "firewall",      x: 6,  y: 4,  w: 6,  h: 5, minW: 4,  minH: 4 },
  { i: "scan_adguard",  x: 0,  y: 9,  w: 12, h: 4, minW: 6,  minH: 3 },
  { i: "speed_chart",   x: 0,  y: 13, w: 12, h: 5, minW: 6,  minH: 4 },
  { i: "events",        x: 0,  y: 18, w: 8,  h: 7, minW: 4,  minH: 5 },
  { i: "notifications", x: 8,  y: 18, w: 4,  h: 4, minW: 3,  minH: 3 },
];

function loadLayout(): Layout[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved) as Layout[];
      // Merge with defaults to pick up any new widgets added in updates
      const savedIds = new Set(parsed.map((l) => l.i));
      const newDefaults = DEFAULT_LAYOUT.filter((l) => !savedIds.has(l.i));
      return [...parsed, ...newDefaults];
    }
  } catch {
    // ignore parse errors
  }
  return DEFAULT_LAYOUT;
}

function saveLayout(layout: Layout[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
  } catch {
    // ignore storage errors
  }
}

export function useDashboardLayout() {
  const [layout, setLayout] = useState<Layout[]>(loadLayout);
  const [editMode, setEditMode] = useState(false);

  const onLayoutChange = useCallback((newLayout: Layout[]) => {
    setLayout(newLayout);
    saveLayout(newLayout);
  }, []);

  const resetLayout = useCallback(() => {
    setLayout(DEFAULT_LAYOUT);
    saveLayout(DEFAULT_LAYOUT);
  }, []);

  return { layout, editMode, setEditMode, onLayoutChange, resetLayout };
}
