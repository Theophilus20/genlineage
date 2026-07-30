from __future__ import annotations

from pathlib import Path

from ..config import settings
from .base import Storage, asset_key, sha256_hex


class LocalStorage(Storage):
    """Filesystem mirror of the B2 layout, for keyless local dev."""

    def __init__(self, root: Path | None = None):
        self.root = root or settings.LOCAL_DATA_DIR
        for d in ("assets", "derivatives", "provenance", "graph", "failures"):
            (self.root / d).mkdir(parents=True, exist_ok=True)

    def _asset_path(self, digest: str, ext: str) -> Path:
        return self.root / "assets" / asset_key(digest, ext)

    def put_asset(self, data: bytes, ext: str) -> str:
        digest = sha256_hex(data)
        path = self._asset_path(digest, ext)
        if not path.exists():  # content-addressing = free dedup
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return digest

    def has_asset(self, digest: str, ext: str) -> bool:
        return self._asset_path(digest, ext).exists()

    def asset_url(self, digest: str, ext: str) -> str:
        return f"/api/assets/{digest}.{ext}"

    def get_asset(self, digest: str, ext: str) -> bytes:
        return self._asset_path(digest, ext).read_bytes()

    def put_provenance(self, digest: str, name: str, data: bytes) -> None:
        p = self.root / "provenance" / digest
        p.mkdir(parents=True, exist_ok=True)
        (p / name).write_bytes(data)

    def get_provenance(self, digest: str, name: str) -> bytes | None:
        p = self.root / "provenance" / digest / name
        return p.read_bytes() if p.exists() else None

    def append_dag(self, project_id: str, line: str) -> None:
        p = self.root / "graph" / "projects" / project_id
        p.mkdir(parents=True, exist_ok=True)
        with open(p / "dag.jsonl", "a") as f:
            f.write(line.rstrip("\n") + "\n")

    def read_dag(self, project_id: str) -> list[str]:
        p = self.root / "graph" / "projects" / project_id / "dag.jsonl"
        if not p.exists():
            return []
        return [ln for ln in p.read_text().splitlines() if ln.strip()]

    def delete_dag(self, project_id: str) -> None:
        import shutil
        p = self.root / "graph" / "projects" / project_id
        if p.exists():
            shutil.rmtree(p)

    def put_failure(self, job_id: str, attempt: int, ext: str, data: bytes) -> str:
        p = self.root / "failures" / job_id
        p.mkdir(parents=True, exist_ok=True)
        path = p / f"attempt-{attempt}.{ext}"
        path.write_bytes(data)
        return str(path)
