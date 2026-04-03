from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime


class ReviewRequest(BaseModel):
    pr_url: str


class Finding(BaseModel):
    file: str
    line_range: str        # e.g. "12-18"
    severity: str          # critical | high | medium | low
    category: str          # security | logic | style
    description: str
    suggestion: str


class ReviewMetrics(BaseModel):
    total_issues: int
    severity_breakdown: dict[str, int]
    latency_per_node: dict[str, float]
    total_latency_ms: float
    mode: str


class ReviewResponse(BaseModel):
    id: int
    pr_url: str
    pr_metadata: dict
    findings: list[Finding]
    summary: str
    metrics: ReviewMetrics
    created_at: datetime


class ReviewHistoryItem(BaseModel):
    id: int
    pr_url: str
    mode: str
    total_issues: int
    total_latency_ms: float
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
