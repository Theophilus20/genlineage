from __future__ import annotations

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ..config import settings
from .base import Storage, asset_key, sha256_hex

PRESIGN_TTL = 3600  # seconds


class B2Storage(Storage):
    """Backblaze B2 through its S3-compatible API.

    Five buckets, per the architecture doc. Lifecycle rule to configure once
    in the B2 console: genlineage-failures → delete files older than 7 days.
    """

    def _loc(self, kind: str, key: str) -> tuple[str, str]:
        """(bucket, key) for a logical store. With B2_BUCKET set, everything
        lives in one bucket under kind prefixes; otherwise five buckets."""
        if settings.B2_BUCKET:
            return settings.B2_BUCKET, f"{kind}/{key}"
        buckets = {"assets": settings.BUCKET_ASSETS,
                   "provenance": settings.BUCKET_PROVENANCE,
                   "graph": settings.BUCKET_GRAPH,
                   "failures": settings.BUCKET_FAILURES}
        return buckets[kind], key

    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=settings.B2_ENDPOINT,
            aws_access_key_id=settings.B2_KEY_ID,
            aws_secret_access_key=settings.B2_APP_KEY,
            config=Config(signature_version="s3v4"),
        )

    def healthcheck(self) -> None:
        """Fail fast if the keys/endpoint/buckets don't actually work.

        Called once when storage is selected, so a bad key surfaces as a clear
        warning at startup instead of a 500 in the middle of a pipeline run.
        """
        bucket, _ = self._loc("graph", "")
        self.s3.list_objects_v2(Bucket=bucket, MaxKeys=1)

    # -- assets ---------------------------------------------------------------
    def put_asset(self, data: bytes, ext: str) -> str:
        digest = sha256_hex(data)
        bucket, key = self._loc("assets", asset_key(digest, ext))
        if not self._exists(bucket, key):
            self.s3.put_object(Bucket=bucket, Key=key, Body=data)
        return digest

    def has_asset(self, digest: str, ext: str) -> bool:
        return self._exists(*self._loc("assets", asset_key(digest, ext)))

    def asset_url(self, digest: str, ext: str) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params=dict(zip(("Bucket", "Key"),
                            self._loc("assets", asset_key(digest, ext)))),
            ExpiresIn=PRESIGN_TTL,
        )

    def get_asset(self, digest: str, ext: str) -> bytes:
        bucket, key = self._loc("assets", asset_key(digest, ext))
        obj = self.s3.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()

    # -- provenance -------------------------------------------------------------
    def put_provenance(self, digest: str, name: str, data: bytes) -> None:
        bucket, key = self._loc("provenance", f"{digest}/{name}")
        self.s3.put_object(Bucket=bucket, Key=key, Body=data)

    def get_provenance(self, digest: str, name: str) -> bytes | None:
        try:
            bucket, key = self._loc("provenance", f"{digest}/{name}")
            obj = self.s3.get_object(Bucket=bucket, Key=key)
            return obj["Body"].read()
        except ClientError:
            return None

    # -- graph ---------------------------------------------------------------------
    # S3 has no append; we emulate an append-only log with one object per commit
    # plus a read that concatenates in key order (keys are zero-padded seq numbers).
    def append_dag(self, project_id: str, line: str) -> None:
        bucket, prefix = self._loc("graph", f"projects/{project_id}/dag/")
        n = len(self._list(bucket, prefix))
        self.s3.put_object(Bucket=bucket, Key=f"{prefix}{n:08d}.json",
                           Body=line.encode())

    def read_dag(self, project_id: str) -> list[str]:
        bucket, prefix = self._loc("graph", f"projects/{project_id}/dag/")
        lines = []
        for key in sorted(self._list(bucket, prefix)):
            obj = self.s3.get_object(Bucket=bucket, Key=key)
            lines.append(obj["Body"].read().decode())
        return lines

    def delete_dag(self, project_id: str) -> None:
        bucket, prefix = self._loc("graph", f"projects/{project_id}/dag/")
        keys = self._list(bucket, prefix)
        for i in range(0, len(keys), 1000):
            self.s3.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]]},
            )

    # -- failures ---------------------------------------------------------------------
    def put_failure(self, job_id: str, attempt: int, ext: str, data: bytes) -> str:
        bucket, key = self._loc("failures", f"{job_id}/attempt-{attempt}.{ext}")
        self.s3.put_object(Bucket=bucket, Key=key, Body=data)
        return f"b2://{bucket}/{key}"

    # -- helpers -----------------------------------------------------------------------
    def _exists(self, bucket: str, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    def _list(self, bucket: str, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            keys.extend(o["Key"] for o in page.get("Contents", []))
        return keys
