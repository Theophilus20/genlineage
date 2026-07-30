"""Content-addressed storage.

B2 is the source of truth; Postgres/SQLite is only an index.
Layout (identical for local dev and B2):

  assets/sha256/ab/cd/<hash>.<ext>          immutable, content-addressed
  derivatives/<hash>/thumb.webp
  provenance/<hash>/manifest.json           signed recipe + lineage
  provenance/<hash>/eval_log.json           every attempt, score, cost
  graph/projects/<id>/dag.jsonl             append-only commit log
  failures/<job>/<attempt>.<ext>            rejects (lifecycle: delete 7d)
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def asset_key(digest: str, ext: str) -> str:
    return f"sha256/{digest[:2]}/{digest[2:4]}/{digest}.{ext}"


class Storage(ABC):
    """Five logical buckets behind one interface."""

    # -- assets (immutable) --------------------------------------------------
    @abstractmethod
    def put_asset(self, data: bytes, ext: str) -> str:
        """Store bytes; returns sha256 digest. Idempotent (free dedup)."""

    @abstractmethod
    def has_asset(self, digest: str, ext: str) -> bool: ...

    @abstractmethod
    def asset_url(self, digest: str, ext: str) -> str:
        """URL the frontend can stream from (presigned on B2, API route locally)."""

    @abstractmethod
    def get_asset(self, digest: str, ext: str) -> bytes: ...

    # -- provenance ------------------------------------------------------------
    @abstractmethod
    def put_provenance(self, digest: str, name: str, data: bytes) -> None: ...

    @abstractmethod
    def get_provenance(self, digest: str, name: str) -> bytes | None: ...

    # -- graph (append-only) ----------------------------------------------------
    @abstractmethod
    def append_dag(self, project_id: str, line: str) -> None: ...

    @abstractmethod
    def read_dag(self, project_id: str) -> list[str]: ...

    def delete_dag(self, project_id: str) -> None:
        """Remove a project's DAG log (project deletion). Default: no-op."""
        return None

    # -- failures -----------------------------------------------------------------
    @abstractmethod
    def put_failure(self, job_id: str, attempt: int, ext: str, data: bytes) -> str: ...
