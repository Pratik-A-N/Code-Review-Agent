"""
PR Ingester Node
Fetches PR diff + metadata from GitHub REST API using GITHUB_TOKEN.
Falls back to unauthenticated requests (lower rate limits) if token absent.
"""
import re
import time
import httpx
from graph.state import AgentState
from config import GITHUB_TOKEN


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Extract owner, repo, pr_number from a GitHub PR URL."""
    pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(pattern, pr_url)
    if not match:
        raise ValueError(f"Cannot parse GitHub PR URL: {pr_url}")
    owner, repo, number = match.groups()
    return owner, repo, int(number)


def pr_ingester(state: AgentState) -> AgentState:
    start = time.time()
    metrics = state.get("metrics", {})
    metrics.setdefault("latency_per_node", {})

    try:
        owner, repo, pr_number = parse_pr_url(state["pr_url"])
        print(owner, repo, pr_number)
        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        with httpx.Client(timeout=30) as client:
            # Fetch PR metadata
            meta_resp = client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=headers,
            )
            meta_resp.raise_for_status()
            pr_data = meta_resp.json()

            # Fetch diff
            diff_headers = {**headers, "Accept": "application/vnd.github.v3.diff"}
            diff_resp = client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=diff_headers,
            )
            diff_resp.raise_for_status()
            raw_diff = diff_resp.text

        pr_metadata = {
            "title": pr_data.get("title", ""),
            "author": pr_data.get("user", {}).get("login", ""),
            "base_branch": pr_data.get("base", {}).get("ref", ""),
            "head_branch": pr_data.get("head", {}).get("ref", ""),
            "additions": pr_data.get("additions", 0),
            "deletions": pr_data.get("deletions", 0),
            "changed_files": pr_data.get("changed_files", 0),
        }

        elapsed = (time.time() - start) * 1000
        metrics["latency_per_node"]["pr_ingester"] = round(elapsed, 2)

        return {
            **state,
            "pr_metadata": pr_metadata,
            "raw_diff": raw_diff,
            "metrics": metrics,
            "error": None,
        }

    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        metrics["latency_per_node"]["pr_ingester"] = round(elapsed, 2)
        return {**state, "metrics": metrics, "error": f"pr_ingester failed: {exc}"}
