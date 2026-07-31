"""Genlineage server configuration.

Everything is env-driven. With no keys set, the stack runs fully local:
mock providers, mock planner/evaluator, filesystem content store.
Set the relevant keys and the real clients switch on per-subsystem.
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # load server/.env if present, so keys Just Work on any OS
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:  # load server/.env so keys pasted there just work
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _flag(name: str, default: str = "") -> str:
    # empty values in .env (e.g. "DATABASE_URL=") must not override defaults
    return os.environ.get(name, "").strip() or default.strip()


class Settings:
    # --- storage -----------------------------------------------------------
    B2_KEY_ID = _flag("B2_KEY_ID")
    B2_APP_KEY = _flag("B2_APP_KEY")
    B2_ENDPOINT = _flag("B2_ENDPOINT")  # e.g. https://s3.us-west-004.backblazeb2.com
    # Single-bucket mode: set B2_BUCKET and all stores become prefixes inside
    # it (assets/, provenance/, graph/, failures/) — one bucket to create.
    B2_BUCKET = _flag("B2_BUCKET")
    BUCKET_ASSETS = _flag("B2_BUCKET_ASSETS", "genlineage-assets")
    BUCKET_DERIVATIVES = _flag("B2_BUCKET_DERIVATIVES", "genlineage-derivatives")
    BUCKET_PROVENANCE = _flag("B2_BUCKET_PROVENANCE", "genlineage-provenance")
    BUCKET_GRAPH = _flag("B2_BUCKET_GRAPH", "genlineage-graph")
    BUCKET_FAILURES = _flag("B2_BUCKET_FAILURES", "genlineage-failures")
    LOCAL_DATA_DIR = Path(_flag("GENLINEAGE_DATA_DIR", str(Path.cwd() / "data")))

    # --- providers ---------------------------------------------------------
    FAL_KEY = _flag("FAL_KEY")
    REPLICATE_API_TOKEN = _flag("REPLICATE_API_TOKEN")
    ELEVENLABS_API_KEY = _flag("ELEVENLABS_API_KEY")
    GEMINI_API_KEY = _flag("GEMINI_API_KEY")
    GEMINI_IMAGE_MODEL = _flag("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    GEMINI_TTS_MODEL = _flag("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    # free-tier pacing: seconds between Gemini calls, retries on 429
    GEMINI_MIN_INTERVAL = float(_flag("GEMINI_MIN_INTERVAL", "6"))
    GEMINI_429_RETRIES = int(_flag("GEMINI_429_RETRIES", "2"))

    # --- OpenRouter (openrouter.ai/keys) — unified video generation ---------
    OPENROUTER_API_KEY = _flag("OPENROUTER_API_KEY")
    OPENROUTER_VIDEO_MODEL = _flag("OPENROUTER_VIDEO_MODEL", "google/veo-3.1-lite")
    OPENROUTER_VIDEO_RESOLUTION = _flag("OPENROUTER_VIDEO_RESOLUTION", "720p")
    OPENROUTER_VIDEO_DURATION = _flag("OPENROUTER_VIDEO_DURATION", "6")

    # --- email via Resend ---------------------------------------------------
    RESEND_API_KEY = _flag("RESEND_API_KEY")
    MAIL_FROM = _flag("MAIL_FROM", "Genlineage <no-reply@genlineage.xyz>")
    SUPPORT_EMAIL = _flag("SUPPORT_EMAIL", "support@genlineage.xyz")
    SUPPORT_FROM = _flag("SUPPORT_FROM", "Genlineage Support <support@genlineage.xyz>")
    # --- Cloudflare Turnstile (bot protection) ---
    TURNSTILE_SITE_KEY = _flag("TURNSTILE_SITE_KEY")
    TURNSTILE_SECRET = _flag("TURNSTILE_SECRET")

    # --- Google sign-in (console.cloud.google.com -> OAuth 2.0 Client ID) ---
    GOOGLE_CLIENT_ID = _flag("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = _flag("GOOGLE_CLIENT_SECRET")

    # Force mock even if keys exist (cheap local dev / CI)
    MOCK_MODE = _flag("GENLINEAGE_MOCK", "auto")  # "auto" | "1" | "0"

    # --- pipeline ----------------------------------------------------------
    QUALITY_GATE_MIN = float(_flag("QUALITY_GATE_MIN", "7.0"))  # rubric is 0-10
    MAX_ATTEMPTS_PER_PROVIDER = int(_flag("MAX_ATTEMPTS_PER_PROVIDER", "2"))

    # --- billing: Flutterwave ------------------------------------------------
    FLW_SECRET_KEY = _flag("FLW_SECRET_KEY")      # from the Flutterwave dashboard
    FLW_PUBLIC_KEY = _flag("FLW_PUBLIC_KEY")
    FLW_WEBHOOK_HASH = _flag("FLW_WEBHOOK_HASH")  # dashboard → Settings → Webhooks
    FLW_CURRENCY = _flag("FLW_CURRENCY", "NGN")   # settle in your account currency
    # set FLW_RECURRING=0 to charge one-off instead of subscribing (diagnostics)
    FLW_RECURRING = _flag("FLW_RECURRING", "1") not in ("0", "false", "no")
    # only used when FLW_RECURRING=0 (a payment_plan forces card-only)
    FLW_PAYMENT_OPTIONS = _flag("FLW_PAYMENT_OPTIONS",
                                "card,banktransfer,ussd,account")
    APP_URL = _flag("GENLINEAGE_APP_URL", "http://localhost:3000")
    # the API's own public address (Google redirects back here)
    API_URL = _flag("GENLINEAGE_API_URL", "http://localhost:8000")

    # --- index db ----------------------------------------------------------
    DATABASE_URL = _flag("DATABASE_URL", "sqlite:///./genlineage.db")

    # --- signing -----------------------------------------------------------
    # hex-encoded ed25519 seed; generated & persisted on first boot if absent
    SIGNING_KEY = _flag("GENLINEAGE_SIGNING_KEY")
    SIGNING_KEY_FILE = Path(_flag("GENLINEAGE_SIGNING_KEY_FILE", ".signing_key"))

    @property
    def b2_enabled(self) -> bool:
        return bool(self.B2_KEY_ID and self.B2_APP_KEY and self.B2_ENDPOINT)

    @property
    def flw_enabled(self) -> bool:
        return bool(self.FLW_SECRET_KEY)

    @property
    def cookie_secure(self) -> bool:
        return self.APP_URL.startswith("https://")

    @property
    def mail_enabled(self) -> bool:
        return bool(self.RESEND_API_KEY)

    @property
    def google_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    def provider_is_live(self, provider: str) -> bool:
        if self.MOCK_MODE == "1":
            return False
        keys = {
            "fal": self.FAL_KEY,
            "replicate": self.REPLICATE_API_TOKEN,
            "elevenlabs": self.ELEVENLABS_API_KEY,
            "gemini": self.GEMINI_API_KEY,
            "openrouter": self.OPENROUTER_API_KEY,
        }
        return bool(keys.get(provider))


settings = Settings()
