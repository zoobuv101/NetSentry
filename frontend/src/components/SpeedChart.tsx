import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/api/client";

interface SpeedEntry {
  download_mbps: number;
  upload_mbps: number;
  ping_ms: number;
  tested_at: string | null;
  grade: string | null;
}

function formatDate(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function SpeedChart() {
  const [data, setData] = useState<SpeedEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSpeedTestHistory()
      .then((res) => {
        const results = (res as { results: SpeedEntry[] }).results;
        setData([...results].reverse()); // oldest first for chart
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-sm text-gray-400">
        Loading speed history…
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-sm text-gray-400">
        No speed tests yet. Run your first test to see results here.
      </div>
    );
  }

  const chartData = data.map((d) => ({
    name: d.tested_at ? formatDate(d.tested_at) : "",
    "Download (Mbps)": Math.round(d.download_mbps * 10) / 10,
    "Upload (Mbps)": Math.round(d.upload_mbps * 10) / 10,
    "Ping (ms)": Math.round(d.ping_ms * 10) / 10,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="Download (Mbps)" stroke="#2563eb" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="Upload (Mbps)" stroke="#16a34a" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
