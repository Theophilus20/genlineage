"""Genblaze SDK integration.

Every Genlineage commit also produces an official Genblaze provenance
manifest (genblaze-core): a canonical, SHA-256-bound record of the run,
step, and output asset — signed with our ed25519 key and persisted next to
the asset in storage (Backblaze B2 in production).

This gives each output two interoperable provenance records: our native
remix-DAG manifest and the Backblaze-standard Genblaze manifest, verifiable
with the genblaze CLI (`genblaze verify`).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


def build_manifest(*, job_id: str, project_id: str, brief: str, step_id: str,
                   provider: str, model: str, modality: str, prompt: str,
                   seed: int, params: dict, parents: list[str],
                   asset_sha256: str, asset_url: str, media_type: str,
                   size_bytes: int, cost_usd: float,
                   sign) -> bytes | None:
    """Canonical Genblaze manifest JSON for one committed asset (or None if
    the SDK is unavailable — provenance must never break a run)."""
    try:
        from genblaze_core.canonical.json import canonical_json
        from genblaze_core.models.asset import Asset
        from genblaze_core.models.manifest import Manifest, canonical_hash
        from genblaze_core.models.run import Run
        from genblaze_core.models.step import Step

        now = datetime.now(timezone.utc).isoformat()
        step = Step(
            step_id=step_id,
            run_id=job_id,
            provider=provider,
            model=model,
            modality={"voice": "audio"}.get(modality, modality),
            prompt=prompt,
            seed=seed,
            params={k: v for k, v in (params or {}).items()
                    if isinstance(v, (str, int, float, bool))},
            status="succeeded",
            inputs=list(parents or []),
            cost_usd=cost_usd,
            completed_at=now,
            assets=[Asset(url=asset_url, media_type=media_type,
                          sha256=asset_sha256, size_bytes=size_bytes)],
        )
        run = Run(run_id=job_id, project_id=project_id, name=brief[:120],
                  status="completed", steps=[step], completed_at=now)
        manifest = Manifest(run=run)
        digest = canonical_hash(manifest.model_dump(exclude_none=True,
                                                    exclude={"canonical_hash",
                                                             "signature"}))
        manifest.canonical_hash = digest
        manifest.signature = sign(digest.encode()) if sign else None
        return canonical_json(manifest.model_dump(exclude_none=True)).encode()
    except Exception:
        return None


def verify_manifest(raw: bytes) -> dict:
    """Re-derive the canonical hash and report whether it matches."""
    try:
        from genblaze_core.models.manifest import canonical_hash, parse_manifest
        m = parse_manifest(json.loads(raw.decode()))
        expect = m.canonical_hash
        actual = canonical_hash(m.model_dump(exclude_none=True,
                                             exclude={"canonical_hash",
                                                      "signature"}))
        return {"ok": bool(expect) and expect == actual,
                "canonical_hash": expect,
                "schema_version": m.schema_version,
                "signature": m.signature}
    except Exception as e:
        return {"ok": False, "error": str(e)}
