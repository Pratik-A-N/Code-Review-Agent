import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from models.schemas import (
    ReviewRequest,
    ReviewResponse,
    ReviewHistoryItem,
    HealthResponse,
    Finding,
    ReviewMetrics,
)
from graph.pipeline import pipeline
from graph.progress import register as register_progress, unregister as unregister_progress
from db.database import init_db, save_review, get_review, list_reviews

app = FastAPI(title="Code Review Agent", version="1.0.0")

# ---------------------------------------------------------------------------
# CORS — read from CORS_ORIGINS env var (comma-separated), fallback to dev defaults
# ---------------------------------------------------------------------------

_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory async job store  {job_id (uuid str) -> {"queue": Queue, "status": str}}
# Jobs are cleaned up after the SSE stream closes.
# ---------------------------------------------------------------------------

_jobs: Dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup():
    init_db()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_initial_state(pr_url: str, mode: str, review_id: str | None = None) -> dict:
    return {
        "review_id": review_id,
        "pr_url": pr_url,
        "pr_metadata": {},
        "raw_diff": "",
        "file_chunks": [],
        "security_findings": [],
        "logic_findings": [],
        "style_findings": [],
        "aggregated_findings": [],
        "review_summary": "",
        "metrics": {"latency_per_node": {}},
        "error": None,
        "mode": mode,
    }


def _build_response_from_result(pr_url: str, mode: str, result: dict) -> ReviewResponse:
    """Process raw pipeline result into a ReviewResponse and persist to DB."""
    if result.get("error") and not result.get("aggregated_findings"):
        raise HTTPException(status_code=422, detail=result["error"])

    metrics_raw = result.get("metrics", {})
    review_metrics = ReviewMetrics(
        total_issues=metrics_raw.get("total_issues", 0),
        severity_breakdown=metrics_raw.get("severity_breakdown", {}),
        latency_per_node=metrics_raw.get("latency_per_node", {}),
        total_latency_ms=metrics_raw.get("total_latency_ms", 0.0),
        mode=mode,
    )
    findings = [Finding(**f) for f in result.get("aggregated_findings", [])]
    db_id = save_review(
        pr_url=pr_url,
        mode=mode,
        pr_metadata=result.get("pr_metadata", {}),
        findings=[f.model_dump() for f in findings],
        summary=result.get("review_summary", ""),
        metrics=metrics_raw,
    )
    return ReviewResponse(
        id=db_id,
        pr_url=pr_url,
        pr_metadata=result.get("pr_metadata", {}),
        findings=findings,
        summary=result.get("review_summary", ""),
        metrics=review_metrics,
        created_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# Synchronous review endpoint (kept for API consumers who don't want SSE)
# ---------------------------------------------------------------------------

@app.post("/api/review", response_model=ReviewResponse)
def run_review(
    body: ReviewRequest,
    mode: str = Query(default="agent", pattern="^(agent|baseline)$"),
):
    result = pipeline.invoke(_make_initial_state(body.pr_url, mode))
    return _build_response_from_result(body.pr_url, mode, result)


# ---------------------------------------------------------------------------
# Async review — POST starts job, GET /{job_id}/stream delivers SSE progress
# ---------------------------------------------------------------------------

@app.post("/api/review/async")
async def start_async_review(
    body: ReviewRequest,
    mode: str = Query(default="agent", pattern="^(agent|baseline)$"),
):
    """Start a review asynchronously. Returns a review_id to open the SSE stream."""
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    _jobs[job_id] = {"queue": queue, "status": "running"}
    register_progress(job_id, queue, loop)

    asyncio.create_task(_run_pipeline_background(job_id, body.pr_url, mode))
    return {"review_id": job_id}


async def _run_pipeline_background(job_id: str, pr_url: str, mode: str) -> None:
    queue: asyncio.Queue = _jobs[job_id]["queue"]
    try:
        initial_state = _make_initial_state(pr_url, mode, review_id=job_id)
        result = await asyncio.to_thread(pipeline.invoke, initial_state)
        response = _build_response_from_result(pr_url, mode, result)
        await queue.put({"type": "result", "data": response.model_dump(mode="json")})
    except HTTPException as exc:
        await queue.put({"type": "error", "message": exc.detail})
    except Exception as exc:
        await queue.put({"type": "error", "message": str(exc)})
    finally:
        await queue.put(None)  # sentinel — tells the SSE generator to stop
        if job_id in _jobs:
            _jobs[job_id]["status"] = "done"
        unregister_progress(job_id)


@app.get("/api/review/{job_id}/stream")
async def stream_review_progress(job_id: str):
    """SSE stream — emits node progress events then the final review result."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Review job not found")

    queue: asyncio.Queue = _jobs[job_id]["queue"]

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}  # keep-alive
                    continue

                if event is None:  # sentinel — pipeline finished
                    break
                yield {"data": json.dumps(event)}
        finally:
            _jobs.pop(job_id, None)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Review history
# ---------------------------------------------------------------------------

@app.get("/api/reviews", response_model=list[ReviewHistoryItem])
def get_reviews():
    rows = list_reviews()
    return [
        ReviewHistoryItem(
            id=r["id"],
            pr_url=r["pr_url"],
            mode=r["mode"],
            total_issues=r.get("metrics", {}).get("total_issues", 0),
            total_latency_ms=r.get("metrics", {}).get("total_latency_ms", 0.0),
            created_at=datetime.fromisoformat(r["created_at"]),
        )
        for r in rows
    ]


@app.get("/api/reviews/{review_id}", response_model=ReviewResponse)
def get_single_review(review_id: int):
    row = get_review(review_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")

    metrics_raw = row.get("metrics", {})
    return ReviewResponse(
        id=row["id"],
        pr_url=row["pr_url"],
        pr_metadata=row.get("pr_metadata", {}),
        findings=[Finding(**f) for f in row.get("findings", [])],
        summary=row.get("summary", ""),
        metrics=ReviewMetrics(
            total_issues=metrics_raw.get("total_issues", 0),
            severity_breakdown=metrics_raw.get("severity_breakdown", {}),
            latency_per_node=metrics_raw.get("latency_per_node", {}),
            total_latency_ms=metrics_raw.get("total_latency_ms", 0.0),
            mode=row.get("mode", "agent"),
        ),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
