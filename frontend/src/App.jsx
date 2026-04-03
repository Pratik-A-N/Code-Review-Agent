import { useState } from "react";
import PRInput from "./components/PRInput";
import ReviewDashboard from "./components/ReviewDashboard";

// Node names as emitted by the backend pipeline
const PIPELINE_NODES = [
  "pr_ingester",
  "code_parser",
  "security_node",
  "logic_node",
  "style_node",
  "aggregator",
  "formatter",
];

const BASELINE_NODES = ["pr_ingester", "baseline"];

export default function App() {
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeNode, setActiveNode] = useState(null);
  const [nodeStatuses, setNodeStatuses] = useState({});
  const [history, setHistory] = useState([]);

  async function handleSubmit(prUrl, mode) {
    setLoading(true);
    setError(null);
    setReview(null);
    setActiveNode(null);
    setNodeStatuses({});

    try {
      // Start async review job
      const startResp = await fetch(`/api/review/async?mode=${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pr_url: prUrl }),
      });

      if (!startResp.ok) {
        let errMsg = "Failed to start review";
        try {
          const body = await startResp.json();
          if (typeof body.detail === "string") errMsg = body.detail;
        } catch {}
        throw new Error(errMsg);
      }

      const { review_id } = await startResp.json();

      // Stream progress via SSE
      await new Promise((resolve, reject) => {
        const es = new EventSource(`/api/review/${review_id}/stream`);

        es.onmessage = (event) => {
          let data;
          try {
            data = JSON.parse(event.data);
          } catch {
            return; // ignore malformed / heartbeat events
          }

          if (data.type === "result") {
            setReview(data.data);
            setHistory((prev) => [data.data, ...prev.slice(0, 9)]);
            es.close();
            resolve();
          } else if (data.type === "error") {
            es.close();
            reject(new Error(data.message || "Review failed"));
          } else if (data.node) {
            // Pipeline node progress event
            setNodeStatuses((prev) => ({ ...prev, [data.node]: data.status }));
            if (data.status === "running") {
              setActiveNode(data.node);
            }
          }
        };

        es.onerror = () => {
          es.close();
          // SSE unavailable — fall back to the synchronous endpoint
          _fallbackSync(prUrl, mode).then(resolve).catch(reject);
        };
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setActiveNode(null);
    }
  }

  async function _fallbackSync(prUrl, mode) {
    const resp = await fetch(`/api/review?mode=${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pr_url: prUrl }),
    });
    if (!resp.ok) {
      let errMsg = "Review failed";
      try {
        const body = await resp.json();
        if (typeof body.detail === "string") errMsg = body.detail;
      } catch {}
      throw new Error(errMsg);
    }
    const data = await resp.json();
    setReview(data);
    setHistory((prev) => [data, ...prev.slice(0, 9)]);
  }

  const displayNodes =
    nodeStatuses["baseline"] !== undefined ? BASELINE_NODES : PIPELINE_NODES;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-3">
          <span className="text-2xl">🔍</span>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Code Review Agent</h1>
            <p className="text-xs text-gray-500">AI-powered PR analysis · LangGraph + Gemini</p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 flex flex-col gap-8">
        <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
          <PRInput onSubmit={handleSubmit} loading={loading} />
        </div>

        {/* Pipeline progress indicator */}
        {loading && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm font-medium text-indigo-800">
                {activeNode
                  ? `Running ${activeNode.replace(/_/g, " ")}…`
                  : "Starting pipeline…"}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {displayNodes.map((node) => {
                const status = nodeStatuses[node];
                return (
                  <span
                    key={node}
                    className={`text-xs px-2 py-1 rounded font-mono transition-all ${
                      status === "running"
                        ? "bg-indigo-600 text-white animate-pulse"
                        : status === "completed"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {status === "completed" ? "✓ " : ""}
                    {node}
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-800 text-sm">
            <strong>Error:</strong> {error}
          </div>
        )}

        {review && <ReviewDashboard review={review} />}
      </main>
    </div>
  );
}
