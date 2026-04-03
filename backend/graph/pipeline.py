"""
LangGraph Pipeline
Agent mode fans out to 3 review agents in true parallel via the Send API.
Each parallel node writes to its own findings field; reducers in AgentState
merge the results before the aggregator runs.

Progress events are emitted to the SSE queue (if review_id is present in state)
before and after each node via the with_progress() wrapper.
"""
import time
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from graph.state import AgentState
from graph.nodes.pr_ingester import pr_ingester
from graph.nodes.code_parser import code_parser
from graph.nodes.review_agents import (
    run_security_agent,
    run_logic_agent,
    run_style_agent,
)
from graph.nodes.aggregator import aggregator
from graph.nodes.formatter import formatter
from graph.progress import emit as emit_progress


# ---------------------------------------------------------------------------
# Node display metadata
# ---------------------------------------------------------------------------

_NODE_MESSAGES = {
    "pr_ingester":   ("Fetching PR data...",         "PR data fetched"),
    "code_parser":   ("Parsing code chunks...",      "Code parsed"),
    "security_node": ("Analyzing security...",       "Security analysis complete"),
    "logic_node":    ("Analyzing logic...",          "Logic analysis complete"),
    "style_node":    ("Analyzing code style...",     "Style analysis complete"),
    "aggregator":    ("Aggregating findings...",     "Findings aggregated"),
    "formatter":     ("Formatting review...",        "Review complete"),
    "baseline":      ("Running baseline review...",  "Baseline review complete"),
}


def with_progress(node_name: str, fn):
    """Wrap a pipeline node to emit SSE progress events before/after execution."""
    running_msg, done_msg = _NODE_MESSAGES.get(node_name, ("Running...", "Done"))

    def wrapper(state: AgentState):
        review_id = state.get("review_id")
        emit_progress(review_id, {
            "node": node_name,
            "status": "running",
            "message": running_msg,
        })
        t = time.time()
        result = fn(state)
        elapsed = round((time.time() - t) * 1000, 2)
        emit_progress(review_id, {
            "node": node_name,
            "status": "completed",
            "message": done_msg,
            "latency_ms": elapsed,
        })
        return result

    return wrapper


# ---------------------------------------------------------------------------
# Parallel agent nodes — each returns only its own findings + latency slice.
# Reducers in AgentState merge these safely when all three complete.
# ---------------------------------------------------------------------------

def security_node(state: AgentState) -> dict:
    if state.get("error"):
        return {}
    findings, ms = run_security_agent(state.get("file_chunks", []))
    return {
        "security_findings": findings,
        "metrics": {"latency_per_node": {"security_agent": round(ms, 2)}},
    }


def logic_node(state: AgentState) -> dict:
    if state.get("error"):
        return {}
    findings, ms = run_logic_agent(state.get("file_chunks", []))
    return {
        "logic_findings": findings,
        "metrics": {"latency_per_node": {"logic_agent": round(ms, 2)}},
    }


def style_node(state: AgentState) -> dict:
    if state.get("error"):
        return {}
    findings, ms = run_style_agent(state.get("file_chunks", []))
    return {
        "style_findings": findings,
        "metrics": {"latency_per_node": {"style_agent": round(ms, 2)}},
    }


# ---------------------------------------------------------------------------
# Baseline node — single LLM call, skips multi-agent pipeline
# ---------------------------------------------------------------------------

def baseline_node(state: AgentState) -> AgentState:
    from llm.factory import llm
    import json

    start = time.time()
    metrics = state.get("metrics", {})
    metrics.setdefault("latency_per_node", {})

    diff = state.get("raw_diff", "")[:8000]
    prompt = f"""You are an expert code reviewer. Review the following PR diff and return a JSON array of findings.
Each finding: {{"file": str, "line_range": "start-end", "severity": "critical|high|medium|low",
  "category": "security|logic|style", "description": str, "suggestion": str}}
Return only the JSON array.
Diff:
{diff}"""

    try:
        text = llm.generate(prompt).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        findings = json.loads(text)
        if not isinstance(findings, list):
            findings = []
    except Exception as exc:
        findings = []
        state = {**state, "error": f"baseline failed: {exc}"}

    elapsed = (time.time() - start) * 1000
    metrics["latency_per_node"]["baseline"] = round(elapsed, 2)

    breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        sev = f.get("severity", "low")
        breakdown[sev] = breakdown.get(sev, 0) + 1

    metrics["total_issues"] = len(findings)
    metrics["severity_breakdown"] = breakdown
    metrics["total_latency_ms"] = round(elapsed, 2)

    summary = f"Baseline review found {len(findings)} issues."
    return {
        **state,
        "aggregated_findings": findings,
        "review_summary": summary,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Fan-out router — returns Send objects for true parallel execution
# ---------------------------------------------------------------------------

def fan_out(state: AgentState):
    """Dispatch all three review agents in parallel via the Send API."""
    if state.get("error"):
        return [Send("formatter", state)]
    return [
        Send("security_node", state),
        Send("logic_node", state),
        Send("style_node", state),
    ]


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_pipeline() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("pr_ingester",   with_progress("pr_ingester",   pr_ingester))
    graph.add_node("code_parser",   with_progress("code_parser",   code_parser))
    graph.add_node("security_node", with_progress("security_node", security_node))
    graph.add_node("logic_node",    with_progress("logic_node",    logic_node))
    graph.add_node("style_node",    with_progress("style_node",    style_node))
    graph.add_node("aggregator",    with_progress("aggregator",    aggregator))
    graph.add_node("formatter",     with_progress("formatter",     formatter))
    graph.add_node("baseline",      with_progress("baseline",      baseline_node))

    graph.set_entry_point("pr_ingester")

    def route_after_ingester(state: AgentState) -> str:
        if state.get("error"):
            return "formatter"
        if state.get("mode") == "baseline":
            return "baseline"
        return "code_parser"

    graph.add_conditional_edges("pr_ingester", route_after_ingester, {
        "code_parser": "code_parser",
        "baseline":    "baseline",
        "formatter":   "formatter",
    })

    graph.add_conditional_edges("code_parser", fan_out)
    graph.add_edge("security_node", "aggregator")
    graph.add_edge("logic_node",    "aggregator")
    graph.add_edge("style_node",    "aggregator")

    graph.add_edge("aggregator", "formatter")
    graph.add_edge("baseline",   END)
    graph.add_edge("formatter",  END)

    return graph.compile()


# Singleton compiled graph
pipeline = build_pipeline()
