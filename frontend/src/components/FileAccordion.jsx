import { useState } from "react";
import SeverityBadge from "./SeverityBadge";

export default function FileAccordion({ filename, findings }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <span className="font-mono text-sm font-medium text-gray-800 truncate">
          {filename}
        </span>
        <div className="flex items-center gap-2 ml-2 shrink-0">
          <span className="text-xs text-gray-500">{findings.length} issue{findings.length !== 1 ? "s" : ""}</span>
          <span className="text-gray-400">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open && (
        <ul className="divide-y divide-gray-100">
          {findings.map((f, i) => (
            <li key={i} className="px-4 py-3 bg-white">
              <div className="flex items-start gap-3">
                <SeverityBadge severity={f.severity} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                    <span className="font-mono">Lines {f.line_range}</span>
                    <span className="capitalize px-1.5 py-0.5 bg-gray-100 rounded">{f.category}</span>
                  </div>
                  <p className="text-sm text-gray-800 mb-1">{f.description}</p>
                  {f.suggestion && (
                    <p className="text-sm text-indigo-700 italic">
                      Suggestion: {f.suggestion}
                    </p>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
