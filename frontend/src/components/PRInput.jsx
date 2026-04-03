import { useState } from "react";

export default function PRInput({ onSubmit, loading }) {
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState("agent");

  function handleSubmit(e) {
    e.preventDefault();
    if (url.trim()) onSubmit(url.trim(), mode);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          GitHub PR URL
        </label>
        <input
          type="url"
          placeholder="https://github.com/owner/repo/pull/123"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div className="flex items-center gap-6">
        <span className="text-sm font-medium text-gray-700">Mode:</span>
        {["agent", "baseline"].map((m) => (
          <label key={m} className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="mode"
              value={m}
              checked={mode === m}
              onChange={() => setMode(m)}
              className="accent-indigo-600"
            />
            <span className="text-sm capitalize">{m === "agent" ? "Multi-Agent" : "Baseline"}</span>
          </label>
        ))}
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-semibold rounded-lg transition-colors"
      >
        {loading ? "Analyzing…" : "Run Code Review"}
      </button>
    </form>
  );
}
