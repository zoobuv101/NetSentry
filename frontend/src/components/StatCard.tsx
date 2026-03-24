interface StatCardProps {
  label: string;
  value: string | number | null;
  sub?: string;
  color?: "green" | "red" | "blue" | "gray" | "yellow";
}

const colorMap: Record<string, string> = {
  green:  "bg-green-50 text-green-700 border-green-200",
  red:    "bg-red-50 text-red-700 border-red-200",
  blue:   "bg-blue-50 text-blue-700 border-blue-200",
  gray:   "bg-gray-50 text-gray-700 border-gray-200",
  yellow: "bg-yellow-50 text-yellow-700 border-yellow-200",
};

export function StatCard({ label, value, sub, color = "gray" }: StatCardProps) {
  return (
    <div className={`rounded-lg border p-4 ${colorMap[color]}`}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</p>
      <p className="mt-1 text-2xl font-bold">
        {value ?? <span className="text-base font-normal opacity-50">—</span>}
      </p>
      {sub && <p className="mt-0.5 text-xs opacity-60">{sub}</p>}
    </div>
  );
}
