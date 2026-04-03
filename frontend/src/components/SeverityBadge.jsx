const COLORS = {
  critical: "bg-red-100 text-red-800 border border-red-300",
  high:     "bg-orange-100 text-orange-800 border border-orange-300",
  medium:   "bg-yellow-100 text-yellow-800 border border-yellow-300",
  low:      "bg-blue-100 text-blue-800 border border-blue-300",
};

export default function SeverityBadge({ severity }) {
  const cls = COLORS[severity] ?? COLORS.low;
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold uppercase ${cls}`}>
      {severity}
    </span>
  );
}
