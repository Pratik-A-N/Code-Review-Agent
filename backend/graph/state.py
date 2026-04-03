from typing import Annotated, TypedDict
import operator


def _merge_metrics(left: dict, right: dict) -> dict:
    """Reducer that deep-merges latency_per_node and overwrites other keys."""
    if not right:
        return left
    merged = {**left}
    if "latency_per_node" in right:
        merged["latency_per_node"] = {
            **merged.get("latency_per_node", {}),
            **right["latency_per_node"],
        }
    for k, v in right.items():
        if k != "latency_per_node":
            merged[k] = v
    return merged


class AgentState(TypedDict):
    review_id: str | None                                    # UUID for SSE job tracking (None for sync calls)
    pr_url: str
    pr_metadata: dict                                        # title, author, base branch
    raw_diff: str
    file_chunks: list[dict]                                  # [{filename, language, diff_chunk}]
    security_findings: Annotated[list[dict], operator.add]  # reducer: parallel writes concat
    logic_findings: Annotated[list[dict], operator.add]
    style_findings: Annotated[list[dict], operator.add]
    aggregated_findings: list[dict]
    review_summary: str
    metrics: Annotated[dict, _merge_metrics]                 # reducer: deep-merges latency keys
    error: str | None                                        # graceful error propagation
    mode: str                                                # "agent" | "baseline"
