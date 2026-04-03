"""
Review Agents Node
Three specialized agents run in parallel via LangGraph Send API.
Each returns a list of findings. Failures are caught and logged, not re-raised.
"""
import json
import time
from graph.state import AgentState
from llm.factory import llm

# ---------------------------------------------------------------------------
# Prompt templates (kept under 500 tokens for Gemini free tier)
# ---------------------------------------------------------------------------

SECURITY_PROMPT = """You are a security code reviewer. Analyze the diff below for:
- SQL/command injection vulnerabilities
- Hardcoded secrets, API keys, or credentials
- Auth/authz bypasses, broken access control
- Unsafe deserialization or eval usage
- XSS / CSRF vectors

For EACH issue found, return a JSON array of objects:
{{"file": str, "line_range": "start-end", "severity": "critical|high|medium|low",
  "category": "security", "description": str, "suggestion": str}}

If no issues, return [].
Diff:
{diff}"""

LOGIC_PROMPT = """You are a logic and bug reviewer. Analyze the diff below for:
- Off-by-one errors, null/undefined dereferences
- Incorrect conditional logic or missing edge cases
- Improper error handling or silent failures
- Race conditions or concurrency bugs
- Unintended side effects

For EACH issue found, return a JSON array of objects:
{{"file": str, "line_range": "start-end", "severity": "critical|high|medium|low",
  "category": "logic", "description": str, "suggestion": str}}

If no issues, return [].
Diff:
{diff}"""

STYLE_PROMPT = """You are a code style and best-practices reviewer. Analyze the diff below for:
- Poor naming conventions or unclear variable names
- Functions/classes that are too long or have too many responsibilities
- Missing or misleading comments on complex logic
- Violations of language-specific best practices
- Dead code or unnecessary complexity

For EACH issue found, return a JSON array of objects:
{{"file": str, "line_range": "start-end", "severity": "medium|low",
  "category": "style", "description": str, "suggestion": str}}

If no issues, return [].
Diff:
{diff}"""


# ---------------------------------------------------------------------------
# Shared LLM call helper
# ---------------------------------------------------------------------------

def _call_llm(prompt: str) -> list[dict]:
    """Call the configured LLM provider and parse the JSON array response."""
    text = llm.generate(prompt).strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        findings = json.loads(text)
        if not isinstance(findings, list):
            return []
        return findings
    except (json.JSONDecodeError, ValueError):
        return []


def _truncate_diff(diff: str, max_chars: int = 6000) -> str:
    """Truncate diff to stay within free-tier input limits."""
    if len(diff) <= max_chars:
        return diff
    return diff[:max_chars] + "\n... [diff truncated]"


# ---------------------------------------------------------------------------
# Individual agent functions (called in parallel by the pipeline)
# ---------------------------------------------------------------------------

def run_security_agent(file_chunks: list[dict]) -> tuple[list[dict], float]:
    start = time.time()
    findings = []
    for chunk in file_chunks:
        try:
            diff = _truncate_diff(chunk["diff_chunk"])
            prompt = SECURITY_PROMPT.format(diff=diff)
            chunk_findings = _call_llm(prompt)
            # Ensure filename is set correctly
            for f in chunk_findings:
                f.setdefault("file", chunk["filename"])
            findings.extend(chunk_findings)
        except Exception as exc:
            findings.append({
                "file": chunk["filename"],
                "line_range": "N/A",
                "severity": "low",
                "category": "security",
                "description": f"Security agent failed for this file: {exc}",
                "suggestion": "Review manually.",
            })
    return findings, (time.time() - start) * 1000


def run_logic_agent(file_chunks: list[dict]) -> tuple[list[dict], float]:
    start = time.time()
    findings = []
    for chunk in file_chunks:
        try:
            diff = _truncate_diff(chunk["diff_chunk"])
            prompt = LOGIC_PROMPT.format(diff=diff)
            chunk_findings = _call_llm(prompt)
            for f in chunk_findings:
                f.setdefault("file", chunk["filename"])
            findings.extend(chunk_findings)
        except Exception as exc:
            findings.append({
                "file": chunk["filename"],
                "line_range": "N/A",
                "severity": "low",
                "category": "logic",
                "description": f"Logic agent failed for this file: {exc}",
                "suggestion": "Review manually.",
            })
    return findings, (time.time() - start) * 1000


def run_style_agent(file_chunks: list[dict]) -> tuple[list[dict], float]:
    start = time.time()
    findings = []
    for chunk in file_chunks:
        try:
            diff = _truncate_diff(chunk["diff_chunk"])
            prompt = STYLE_PROMPT.format(diff=diff)
            chunk_findings = _call_llm(prompt)
            for f in chunk_findings:
                f.setdefault("file", chunk["filename"])
            findings.extend(chunk_findings)
        except Exception as exc:
            findings.append({
                "file": chunk["filename"],
                "line_range": "N/A",
                "severity": "low",
                "category": "style",
                "description": f"Style agent failed for this file: {exc}",
                "suggestion": "Review manually.",
            })
    return findings, (time.time() - start) * 1000


# ---------------------------------------------------------------------------
# LangGraph node — runs all 3 agents; partial failures are tolerated
# ---------------------------------------------------------------------------

def review_agents(state: AgentState) -> AgentState:
    if state.get("error"):
        return state

    metrics = state.get("metrics", {})
    metrics.setdefault("latency_per_node", {})
    file_chunks = state.get("file_chunks", [])

    # Run agents sequentially here; true parallelism is handled by
    # LangGraph Send API at the pipeline level (see pipeline.py).
    # This function is also usable as a single combined node.
    sec_findings, sec_ms = run_security_agent(file_chunks)
    logic_findings, logic_ms = run_logic_agent(file_chunks)
    style_findings, style_ms = run_style_agent(file_chunks)

    metrics["latency_per_node"]["security_agent"] = round(sec_ms, 2)
    metrics["latency_per_node"]["logic_agent"] = round(logic_ms, 2)
    metrics["latency_per_node"]["style_agent"] = round(style_ms, 2)

    return {
        **state,
        "security_findings": sec_findings,
        "logic_findings": logic_findings,
        "style_findings": style_findings,
        "metrics": metrics,
    }
