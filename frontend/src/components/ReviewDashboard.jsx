import FileAccordion from "./FileAccordion";
import MetricsPanel from "./MetricsPanel";
import SeverityBadge from "./SeverityBadge";

function groupByFile(findings) {
  const map = {};
  for (const f of findings) {
    const key = f.file || "unknown";
    if (!map[key]) map[key] = [];
    map[key].push(f);
  }
  return map;
}

export default function ReviewDashboard({ review }) {
  if (!review) return null;

  const { pr_metadata, summary, findings, metrics } = review;
  const byFile = groupByFile(findings ?? []);
  const breakdown = metrics?.severity_breakdown ?? {};

  return (
    <div className="flex flex-col gap-6">
      {/* Summary card */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {pr_metadata?.title || "Pull Request Review"}
            </h2>
            <p className="text-sm text-gray-500">
              by <span className="font-medium">{pr_metadata?.author || "unknown"}</span>
              {" · "}{pr_metadata?.base_branch && (
                <span>into <code className="bg-gray-100 px-1 rounded">{pr_metadata.base_branch}</code></span>
              )}
            </p>
          </div>
          <div className="flex gap-2 flex-wrap justify-end">
            {["critical", "high", "medium", "low"].map((sev) =>
              breakdown[sev] ? (
                <div key={sev} className="flex items-center gap-1">
                  <SeverityBadge severity={sev} />
                  <span className="text-xs text-gray-600">×{breakdown[sev]}</span>
                </div>
              ) : null
            )}
          </div>
        </div>
        <p className="text-sm text-gray-700 leading-relaxed">{summary}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* File findings */}
        <div className="lg:col-span-2 flex flex-col gap-3">
          <h3 className="font-semibold text-gray-800">
            Files Changed ({Object.keys(byFile).length})
          </h3>
          {Object.keys(byFile).length === 0 ? (
            <p className="text-sm text-gray-500 italic">No issues found.</p>
          ) : (
            Object.entries(byFile).map(([file, filefindings]) => (
              <FileAccordion key={file} filename={file} findings={filefindings} />
            ))
          )}
        </div>

        {/* Metrics sidebar */}
        <div>
          <MetricsPanel metrics={metrics} />
        </div>
      </div>
    </div>
  );
}
