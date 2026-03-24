import { useState, useEffect } from "react";

interface NotificationConfig {
  ntfy: { enabled: boolean; url: string | null };
  telegram: { enabled: boolean; chat_id: string | null };
  quiet_hours: { enabled: boolean; start_hour: number; end_hour: number };
}

interface DecoNode {
  mac_address: string;
  model: string | null;
  role: string | null;
  is_online: boolean;
}

interface MeshClient {
  mac_address: string;
  deco_node_mac: string | null;
  band: string | null;
  connection_type: string | null;
}

function StatusPill({ enabled }: { enabled: boolean }) {
  return enabled ? (
    <span className="rounded-full bg-green-100 dark:bg-green-900/30 px-2 py-0.5 text-xs font-medium text-green-800 dark:text-green-400">
      Configured
    </span>
  ) : (
    <span className="rounded-full bg-gray-100 dark:bg-gray-800 px-2 py-0.5 text-xs font-medium text-gray-500 dark:text-gray-400">
      Not configured
    </span>
  );
}

async function sendTestNotification(channel: "ntfy" | "telegram"): Promise<boolean> {
  try {
    const resp = await fetch(`/api/v1/notifications/test/${channel}`, {
      method: "POST",
    });
    return resp.ok;
  } catch {
    return false;
  }
}

export function SettingsPage() {
  const [config, setConfig] = useState<NotificationConfig | null>(null);
  const [topology, setTopology] = useState<{
    nodes: DecoNode[];
    clients: MeshClient[];
  } | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, boolean | null>>({});

  useEffect(() => {
    fetch("/api/v1/notifications/config")
      .then((r) => r.json())
      .then(setConfig)
      .catch(console.error);

    fetch("/api/v1/deco/topology")
      .then((r) => r.json())
      .then(setTopology)
      .catch(console.error);
  }, []);

  async function handleTest(channel: "ntfy" | "telegram") {
    setTesting(channel);
    setTestResult((prev) => ({ ...prev, [channel]: null }));
    const ok = await sendTestNotification(channel);
    setTestResult((prev) => ({ ...prev, [channel]: ok }));
    setTesting(null);
  }

  return (
    <div className="space-y-8">
      <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Settings</h1>

      {/* Notification channels */}
      <section className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div className="border-b border-gray-200 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Push Notifications
          </h2>
        </div>
        <div className="divide-y divide-gray-100 dark:divide-gray-800">
          {/* ntfy */}
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">ntfy</span>
                {config && <StatusPill enabled={config.ntfy.enabled} />}
              </div>
              {config?.ntfy.url && (
                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{config.ntfy.url}</p>
              )}
            </div>
            <button
              onClick={() => handleTest("ntfy")}
              disabled={!config?.ntfy.enabled || testing === "ntfy"}
              className="rounded-md border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40"
            >
              {testing === "ntfy" ? "Sending…" : "Test"}
            </button>
            {testResult.ntfy !== undefined && testResult.ntfy !== null && (
              <span className={`ml-2 text-xs font-medium ${testResult.ntfy ? "text-green-600" : "text-red-600"}`}>
                {testResult.ntfy ? "✓ Sent" : "✗ Failed"}
              </span>
            )}
          </div>

          {/* Telegram */}
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Telegram</span>
                {config && <StatusPill enabled={config.telegram.enabled} />}
              </div>
              {config?.telegram.chat_id && (
                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                  Chat ID: {config.telegram.chat_id}
                </p>
              )}
            </div>
            <button
              onClick={() => handleTest("telegram")}
              disabled={!config?.telegram.enabled || testing === "telegram"}
              className="rounded-md border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40"
            >
              {testing === "telegram" ? "Sending…" : "Test"}
            </button>
            {testResult.telegram !== undefined && testResult.telegram !== null && (
              <span className={`ml-2 text-xs font-medium ${testResult.telegram ? "text-green-600" : "text-red-600"}`}>
                {testResult.telegram ? "✓ Sent" : "✗ Failed"}
              </span>
            )}
          </div>

          {/* Quiet hours */}
          {config?.quiet_hours && (
            <div className="px-5 py-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Quiet Hours</span>
                <StatusPill enabled={config.quiet_hours.enabled} />
              </div>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                {String(config.quiet_hours.start_hour).padStart(2, "0")}:00 –{" "}
                {String(config.quiet_hours.end_hour).padStart(2, "0")}:00 (UTC)
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Deco Topology */}
      <section className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div className="border-b border-gray-200 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Deco Mesh Topology
          </h2>
        </div>
        {!topology ? (
          <div className="px-5 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
            Loading topology…
          </div>
        ) : topology.nodes.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
            No Deco nodes found. Configure DECO_HOST to enable mesh integration.
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {topology.nodes.map((node) => {
              const clients = topology.clients.filter(
                (c) => c.deco_node_mac === node.mac_address
              );
              return (
                <div key={node.mac_address} className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div
                      className={`h-2 w-2 rounded-full ${node.is_online ? "bg-green-500" : "bg-gray-400"}`}
                    />
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {node.model ?? node.mac_address}
                    </span>
                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 capitalize">
                      {node.role ?? "node"}
                    </span>
                    <span className="ml-auto text-xs text-gray-500 dark:text-gray-400 font-mono">
                      {node.mac_address}
                    </span>
                  </div>
                  {clients.length > 0 && (
                    <div className="mt-2 ml-5 space-y-1">
                      {clients.map((c) => (
                        <div
                          key={c.mac_address}
                          className="flex items-center gap-3 text-xs text-gray-600 dark:text-gray-400"
                        >
                          <span className="font-mono">{c.mac_address}</span>
                          {c.band && (
                            <span className="rounded bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5">
                              {c.band}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
