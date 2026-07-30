from __future__ import annotations

from ..config import settings
from .base import Storage, sha256_hex  # noqa: F401

_cached = None
_warned = False


def get_storage() -> Storage:
    """B2 when configured and reachable; otherwise local disk.

    A bad B2 key must not take the whole pipeline down — we verify the
    credentials once, and fall back to local storage with a loud warning if
    they don't work.
    """
    global _cached, _warned
    if _cached is not None:
        return _cached

    from .local import LocalStorage

    if settings.b2_enabled:
        try:
            from .b2 import B2Storage

            store = B2Storage()
            store.healthcheck()      # fails fast on bad key / bucket / endpoint
            _cached = store
            return _cached
        except Exception as e:
            if not _warned:
                print("=" * 72)
                print("[storage] Backblaze B2 is configured but NOT working:")
                print(f"[storage]   {type(e).__name__}: {e}")
                print("[storage] Falling back to LOCAL DISK (server/data/).")
                print("[storage] Fix B2_KEY_ID / B2_APP_KEY / B2_ENDPOINT / buckets")
                print("[storage] in server/.env, or remove them to use local on purpose.")
                print("=" * 72)
                _warned = True

    _cached = LocalStorage()
    return _cached
