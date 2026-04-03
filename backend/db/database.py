import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("reviews.db")


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_url      TEXT NOT NULL,
                mode        TEXT NOT NULL DEFAULT 'agent',
                pr_metadata TEXT,
                findings    TEXT,
                summary     TEXT,
                metrics     TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_review(
    pr_url: str,
    mode: str,
    pr_metadata: dict,
    findings: list[dict],
    summary: str,
    metrics: dict,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reviews (pr_url, mode, pr_metadata, findings, summary, metrics, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pr_url,
                mode,
                json.dumps(pr_metadata),
                json.dumps(findings),
                summary,
                json.dumps(metrics),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_review(review_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        if not row:
            return None
        return _deserialize_row(dict(row))


def list_reviews(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_deserialize_row(dict(r)) for r in rows]


def _deserialize_row(row: dict) -> dict:
    for field in ("pr_metadata", "findings", "metrics"):
        if row.get(field):
            row[field] = json.loads(row[field])
    return row
