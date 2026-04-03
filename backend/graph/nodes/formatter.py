"""
Formatter Node
Produces a final structured review summary using Gemini and computes total latency.
"""
import time
from llm.factory import llm
from graph.state import AgentState

SUMMARY_PROMPT = """You are a senior software engineer writing a concise PR review summary.
Given the findings below, write 2-3 sentences covering:
1. The overall quality of the changes
2. The most important issues to address
3. A final recommendation (approve / request changes / needs discussion)

Findings (JSON):
{findings}

PR: {title} by {author}
"""


def formatter(state: AgentState) -> AgentState:
    start = time.time()
    metrics = state.get("metrics", {})
    metrics.setdefault("latency_per_node", {})

    if state.get("error"):
        # Even on error, return minimal summary
        metrics["total_latency_ms"] = _sum_latency(metrics)
        return {
            **state,
            "review_summary": f"Review could not be completed: {state['error']}",
            "metrics": metrics,
        }

    findings = state.get("aggregated_findings", [])
    pr_meta = state.get("pr_metadata", {})

    try:
        prompt = SUMMARY_PROMPT.format(
            findings=str(findings[:20]),  # cap to avoid token overflow
            title=pr_meta.get("title", "N/A"),
            author=pr_meta.get("author", "N/A"),
        )
        summary = llm.generate(prompt).strip()
    except Exception as exc:
        summary = f"Summary generation failed: {exc}. Review the findings directly."

    elapsed = (time.time() - start) * 1000
    metrics["latency_per_node"]["formatter"] = round(elapsed, 2)
    metrics["total_latency_ms"] = round(_sum_latency(metrics), 2)

    return {**state, "review_summary": summary, "metrics": metrics}


def _sum_latency(metrics: dict) -> float:
    return sum(metrics.get("latency_per_node", {}).values())
