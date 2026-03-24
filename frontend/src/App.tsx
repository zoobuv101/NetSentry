import { useState } from "react";
import { DevicesPage } from "@/pages/DevicesPage";
import { SettingsPage } from "@/pages/SettingsPage";

type Page = "devices" | "settings";

export default function App() {
  const [page, setPage] = useState<Page>("devices");

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-md bg-blue-600 flex items-center justify-center">
                <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
                </svg>
              </div>
              <span className="text-sm font-bold text-gray-900">NetSentry</span>
            </div>
            <nav className="flex items-center gap-1 ml-4">
              {(["devices", "settings"] as Page[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
                    page === p
                      ? "bg-blue-50 text-blue-600"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {p}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {page === "devices" ? <DevicesPage /> : <SettingsPage />}
      </main>
    </div>
  );
}
