"""
Thread-safe progress emitter for SSE streaming.

The LangGraph pipeline runs in a thread (via asyncio.to_thread).
This module lets pipeline nodes safely push events onto the asyncio
event loop's queue so the SSE endpoint can stream them to the client.
"""
import asyncio
from typing import Dict, Tuple

_registry: Dict[str, Tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = {}


def register(review_id: str, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
    _registry[review_id] = (queue, loop)


def unregister(review_id: str) -> None:
    _registry.pop(review_id, None)


def emit(review_id: str | None, event: dict) -> None:
    """Emit a progress event. Safe to call from any thread."""
    if not review_id or review_id not in _registry:
        return
    queue, loop = _registry[review_id]
    try:
        loop.call_soon_threadsafe(queue.put_nowait, event)
    except Exception:
        pass  # Never crash the pipeline due to a progress event failure
