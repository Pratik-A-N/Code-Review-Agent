"""
Code Parser Node
Splits the raw unified diff into per-file chunks with language detection.
"""
import re
import time
from graph.state import AgentState

LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".sh": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
}


def detect_language(filename: str) -> str:
    for ext, lang in LANGUAGE_MAP.items():
        if filename.endswith(ext):
            return lang
    return "unknown"


def split_diff_by_file(raw_diff: str) -> list[dict]:
    """Parse unified diff into per-file chunks."""
    chunks = []
    current_file = None
    current_lines: list[str] = []

    for line in raw_diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current_file:
                chunks.append({
                    "filename": current_file,
                    "language": detect_language(current_file),
                    "diff_chunk": "".join(current_lines),
                })
            # Extract filename from "diff --git a/foo.py b/foo.py"
            match = re.search(r" b/(.+)$", line.strip())
            current_file = match.group(1) if match else "unknown"
            current_lines = [line]
        elif current_file is not None:
            current_lines.append(line)

    if current_file and current_lines:
        chunks.append({
            "filename": current_file,
            "language": detect_language(current_file),
            "diff_chunk": "".join(current_lines),
        })

    return chunks


def code_parser(state: AgentState) -> AgentState:
    start = time.time()
    metrics = state.get("metrics", {})
    metrics.setdefault("latency_per_node", {})

    if state.get("error"):
        return state  # propagate upstream error

    try:
        raw_diff = state.get("raw_diff", "")
        file_chunks = split_diff_by_file(raw_diff)

        elapsed = (time.time() - start) * 1000
        metrics["latency_per_node"]["code_parser"] = round(elapsed, 2)

        return {**state, "file_chunks": file_chunks, "metrics": metrics}

    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        metrics["latency_per_node"]["code_parser"] = round(elapsed, 2)
        return {**state, "metrics": metrics, "error": f"code_parser failed: {exc}"}
