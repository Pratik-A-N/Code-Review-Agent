"""
Aggregator Node
Merges findings from all 3 agents, deduplicates, assigns final severity ordering.
Handles partial results gracefully (missing agent findings → empty list).
"""
import time
from graph.state import AgentState

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _deduplicate(findings: list[dict]) -> list[dict]:
    """Remove near-duplicate findings by (file, line_range, category) key."""
    seen: set[tuple] = set()
    unique = []
    for f in findings:
        key = (f.get("file", ""), f.get("line_range", ""), f.get("category", ""), f.get("description", "")[:60])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def _normalize_severity(finding: dict) -> dict:
    """Ensure severity is always one of the 4 valid values."""
    valid = set(SEVERITY_ORDER.keys())
    if finding.get("severity") not in valid:
        finding["severity"] = "medium"
    return finding


def aggregator(state: AgentState) -> AgentState:
    start = time.time()
    metrics = state.get("metrics", {})
    metrics.setdefault("latency_per_node", {})

    if state.get("error"):
        return state

    all_findings: list[dict] = []
    for source in ("security_findings", "logic_findings", "style_findings"):
        all_findings.extend(state.get(source) or [])

    # Normalize + deduplicate
    all_findings = [_normalize_severity(f) for f in all_findings]
    all_findings = _deduplicate(all_findings)

    # Sort by severity
    all_findings.sort(key=lambda f: SEVERITY_ORDER.get(f.get("severity", "low"), 3))

    # Severity breakdown
    breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in all_findings:
        sev = f.get("severity", "low")
        breakdown[sev] = breakdown.get(sev, 0) + 1

    metrics["total_issues"] = len(all_findings)
    metrics["severity_breakdown"] = breakdown

    elapsed = (time.time() - start) * 1000
    metrics["latency_per_node"]["aggregator"] = round(elapsed, 2)

    return {**state, "aggregated_findings": all_findings, "metrics": metrics}
