import { useState } from "react";
import { DashboardPage } from "@/pages/DashboardPage";
import { DevicesPage } from "@/pages/DevicesPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { useTheme } from "@/hooks/useTheme";

export type Page = "dashboard" | "devices" | "alerts" | "settings";
export type DeviceFilter = "online" | "offline" | "new_today" | null;

export interface NavState {
  page: Page;
  deviceFilter: DeviceFilter;
}

const NAV_ITEMS: { page: Page; label: string }[] = [
  { page: "dashboard", label: "Dashboard" },
  { page: "devices",   label: "Devices"   },
  { page: "alerts",    label: "Alerts"    },
  { page: "settings",  label: "Settings"  },
];

function SunIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <circle cx="12" cy="12" r="5" />
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  );
}

export default function App() {
  const [nav, setNav] = useState<NavState>({ page: "dashboard", deviceFilter: null });
  const { isDark, toggle } = useTheme();

  function navigate(page: Page, deviceFilter: DeviceFilter = null) {
    setNav({ page, deviceFilter });
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors">
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center gap-3">
            {/* Logo */}
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate("dashboard")}>
              <div className="h-7 w-7 rounded-md bg-blue-600 flex items-center justify-center">
                <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
                </svg>
              </div>
              <span className="text-sm font-bold text-gray-900 dark:text-gray-100">NetSentry</span>
            </div>

            {/* Nav */}
            <nav className="flex items-center gap-1 ml-4">
              {NAV_ITEMS.map(({ page, label }) => (
                <button
                  key={page}
                  onClick={() => navigate(page)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    nav.page === page
                      ? "bg-blue-50 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400"
                      : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>

            {/* Dark mode toggle */}
            <button
              onClick={toggle}
              aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
              className="ml-auto rounded-md p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              {isDark ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {nav.page === "dashboard" && <DashboardPage navigate={navigate} />}
        {nav.page === "devices" && (
          <DevicesPage
            key={`${nav.deviceFilter}`}
            initialFilter={nav.deviceFilter}
          />
        )}
        {nav.page === "alerts"   && <AlertsPage />}
        {nav.page === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}
