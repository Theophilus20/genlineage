"""Content-credential signing.

Every merged commit gets a C2PA-style manifest: the full recipe + lineage,
signed with the server's ed25519 key. Anyone holding the public key can
verify an asset's history without trusting the database.
"""
from __future__ import annotations

import json
from nacl.encoding import HexEncoder
from nacl.signing import SigningKey, VerifyKey

from .config import settings

_signing_key: SigningKey | None = None


def _is_local() -> bool:
    url = settings.APP_URL or ""
    return "localhost" in url or "127.0.0.1" in url or not url


def get_signing_key() -> SigningKey:
    global _signing_key
    if _signing_key is not None:
        return _signing_key
    if settings.SIGNING_KEY:
        _signing_key = SigningKey(settings.SIGNING_KEY.encode(), encoder=HexEncoder)
    elif settings.SIGNING_KEY_FILE.exists():
        _signing_key = SigningKey(
            settings.SIGNING_KEY_FILE.read_text().strip().encode(), encoder=HexEncoder
        )
    elif not _is_local():
        # Production hosts have ephemeral disks: auto-generating here would mint
        # a NEW key on every deploy and silently invalidate every manifest ever
        # signed. Fail loudly instead of corrupting provenance.
        raise RuntimeError(
            "GENLINEAGE_SIGNING_KEY is not set and no .signing_key file exists. "
            "Refusing to generate a new signing key in production — every "
            "existing manifest would fail verification. Set the env var to your "
            "key hex: python -c \"print(open('.signing_key','rb').read().hex())\""
        )
    else:
        _signing_key = SigningKey.generate()
        settings.SIGNING_KEY_FILE.write_text(
            _signing_key.encode(encoder=HexEncoder).decode()
        )
    return _signing_key


def public_key_hex() -> str:
    return get_signing_key().verify_key.encode(encoder=HexEncoder).decode()


def canonical(payload: dict) -> bytes:
    """Deterministic JSON bytes — what actually gets signed."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign_manifest(payload: dict) -> dict:
    """Return a signed manifest wrapping the payload."""
    key = get_signing_key()
    sig = key.sign(canonical(payload)).signature.hex()
    return {
        "claim": payload,
        "signature": {"alg": "ed25519", "sig": sig, "public_key": public_key_hex()},
    }


def verify_manifest(manifest: dict) -> bool:
    try:
        vk = VerifyKey(manifest["signature"]["public_key"].encode(), encoder=HexEncoder)
        vk.verify(canonical(manifest["claim"]), bytes.fromhex(manifest["signature"]["sig"]))
        return True
    except Exception:
        return False
