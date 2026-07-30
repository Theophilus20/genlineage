"""Job execution + live events.

A bounded pool of workers pulls from a PRIORITY queue: paid plans are served
before free ones (the "priority generation queue" entitlement), and within a
tier it stays first-come-first-served. Events are appended to the Job row
(durable) and fanned out to in-memory subscriber queues (WebSocket).

Swapping to Redis/RQ for prod means moving `run_job` into an RQ worker with
per-priority queues; the interface here stays the same.
"""
from __future__ import annotations

import itertools
import queue
import threading
from datetime import datetime, timezone

from .models import Job, SessionLocal
from .pipeline.runner import run_job

# lower number = served first
PRIORITY = {"premium": 0, "standard": 1, "free": 2}
WORKERS = 4

_pending: queue.PriorityQueue = queue.PriorityQueue()
_seq = itertools.count()          # FIFO tie-break within a priority band
_subscribers: dict[str, list[queue.Queue]] = {}
_lock = threading.Lock()


def subscribe(job_id: str) -> queue.Queue:
    q: queue.Queue = queue.Queue()
    with _lock:
        _subscribers.setdefault(job_id, []).append(q)
    return q


def unsubscribe(job_id: str, q: queue.Queue) -> None:
    with _lock:
        subs = _subscribers.get(job_id, [])
        if q in subs:
            subs.remove(q)


def _emit(job_id: str):
    def emit(event: str, payload: dict) -> None:
        entry = {"event": event, "at": datetime.now(timezone.utc).isoformat(),
                 **payload}
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            job.events = [*(job.events or []), entry]
            db.commit()
        finally:
            db.close()
        with _lock:
            for q in _subscribers.get(job_id, []):
                q.put(entry)
    return emit


def _worker() -> None:
    while True:
        _prio, _n, job_id = _pending.get()
        emit = _emit(job_id)
        try:
            db = SessionLocal()
            try:
                job = db.get(Job, job_id)
                if job:
                    job.status = "running"
                    db.commit()
            finally:
                db.close()
            run_job(job_id, emit)
        except Exception:
            pass  # already recorded on the job row
        finally:
            with _lock:
                for q in _subscribers.get(job_id, []):
                    q.put(None)  # sentinel: stream over
            _pending.task_done()


for _ in range(WORKERS):
    threading.Thread(target=_worker, daemon=True).start()


def enqueue(job_id: str, plan: str = "free") -> None:
    """Queue a run. Paid plans are dequeued ahead of free ones."""
    _pending.put((PRIORITY.get(plan, 2), next(_seq), job_id))


def queue_position(job_id: str) -> int | None:
    """How many runs are ahead of this one (for honest UI feedback)."""
    ahead = 0
    for prio, n, jid in list(_pending.queue):
        if jid == job_id:
            return ahead
        ahead += 1
    return None
