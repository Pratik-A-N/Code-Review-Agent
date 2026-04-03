const SEV_COLORS = {
  critical: "bg-red-500",
  high:     "bg-orange-400",
  medium:   "bg-yellow-400",
  low:      "bg-blue-400",
};

export default function MetricsPanel({ metrics }) {
  if (!metrics) return null;

  const { total_issues, severity_breakdown, latency_per_node, total_latency_ms, mode } = metrics;
  const breakdown = severity_breakdown ?? {};
  const maxCount = Math.max(...Object.values(breakdown), 1);

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
      <h3 className="font-semibold text-gray-800 mb-4">Review Metrics</h3>

      <div className="grid grid-cols-2 gap-4 mb-5">
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-gray-900">{total_issues}</div>
          <div className="text-xs text-gray-500 mt-1">Total Issues</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-gray-900">{Math.round(total_latency_ms)}ms</div>
          <div className="text-xs text-gray-500 mt-1">Total Latency</div>
        </div>
      </div>

      {/* Severity breakdown bars */}
      <div className="mb-5">
        <div className="text-xs font-medium text-gray-600 mb-2 uppercase tracking-wide">Issues by Severity</div>
        <div className="flex flex-col gap-2">
          {["critical", "high", "medium", "low"].map((sev) => (
            <div key={sev} className="flex items-center gap-2">
              <span className="text-xs text-gray-600 w-14 capitalize">{sev}</span>
              <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-2 rounded-full ${SEV_COLORS[sev]}`}
                  style={{ width: `${((breakdown[sev] ?? 0) / maxCount) * 100}%` }}
                />
              </div>
              <span className="text-xs font-mono text-gray-700 w-4 text-right">{breakdown[sev] ?? 0}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Node latencies */}
      <div>
        <div className="text-xs font-medium text-gray-600 mb-2 uppercase tracking-wide">
          Pipeline Latency ({mode === "baseline" ? "Baseline" : "Multi-Agent"})
        </div>
        <div className="flex flex-col gap-1">
          {Object.entries(latency_per_node ?? {}).map(([node, ms]) => (
            <div key={node} className="flex justify-between text-xs text-gray-600">
              <span className="font-mono">{node}</span>
              <span>{Math.round(ms)}ms</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
