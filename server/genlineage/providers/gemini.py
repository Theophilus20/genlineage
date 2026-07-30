"""Gemini generation — the free-tier live path.

Images: Gemini 2.5 Flash Image via generateContent (responseModalities IMAGE).
Voice:  Gemini TTS via generateContent (responseModalities AUDIO) — returns
        raw 24kHz 16-bit PCM which we wrap into a WAV container.

Both run on the free tier of a personal API key. Video (Veo) and music are
intentionally absent: Veo requires billing and Google exposes no music API,
so those modalities stay on their existing chains.
"""
from __future__ import annotations

import base64
import io
import threading
import time
import wave

import httpx

from ..config import settings
from .base import GenResult, GenSpec, ProviderError

API = "https://generativelanguage.googleapis.com/v1beta/models"

# free-tier pacing: space calls out and back off on 429 instead of dying
_pace_lock = threading.Lock()
_last_call = 0.0


def _paced_post(model: str, body: dict, timeout: int = 120) -> dict:
    global _last_call
    for attempt in range(settings.GEMINI_429_RETRIES + 1):
        with _pace_lock:
            wait = settings.GEMINI_MIN_INTERVAL - (time.time() - _last_call)
            if wait > 0:
                time.sleep(wait)
            _last_call = time.time()
        try:
            return _post(model, body, timeout)
        except ProviderError as e:
            if "rate limited" in str(e) and attempt < settings.GEMINI_429_RETRIES:
                time.sleep(10 * (attempt + 1))   # 10s, 20s
                continue
            raise

IMAGE_MODEL_DEFAULT = "gemini-2.5-flash-image"
TTS_MODEL_DEFAULT = "gemini-2.5-flash-preview-tts"

EXT_FOR_MIME = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def _post(model: str, body: dict, timeout: int = 120) -> dict:
    r = httpx.post(f"{API}/{model}:generateContent",
                   params={"key": settings.GEMINI_API_KEY},
                   json=body, timeout=timeout)
    if r.status_code == 429:
        raise ProviderError("gemini: rate limited (free-tier quota) — retry later")
    if r.status_code != 200:
        raise ProviderError(f"gemini: HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def _inline_parts(payload: dict) -> list[dict]:
    try:
        return payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError) as e:
        raise ProviderError(f"gemini: unexpected response shape: {e}") from e


def gemini_image(spec: GenSpec, route: str) -> GenResult:
    t0 = time.time()
    model = settings.GEMINI_IMAGE_MODEL or IMAGE_MODEL_DEFAULT
    prompt = spec.prompt
    # steer with the product palette when one was extracted from an upload
    palette = spec.params.get("palette")
    if palette:
        hexes = ", ".join("#%02x%02x%02x" % tuple(c) for c in palette)
        prompt += f". Use this brand color palette: {hexes}"
    try:
        out = _paced_post(model, {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        })
        for part in _inline_parts(out):
            blob = part.get("inline_data") or part.get("inlineData")
            if blob and blob.get("mime_type", blob.get("mimeType", "")).startswith("image/"):
                mime = blob.get("mime_type", blob.get("mimeType"))
                data = base64.b64decode(blob["data"])
                return GenResult(
                    data=data, ext=EXT_FOR_MIME.get(mime, "png"),
                    provider=route, model=model,
                    cost_usd=0.0,  # personal free tier
                    latency_ms=int((time.time() - t0) * 1000),
                    params_used={**spec.params, "model": model},
                )
        raise ProviderError("gemini: response contained no image part")
    except httpx.HTTPError as e:
        raise ProviderError(f"gemini: {e}") from e


def _pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def gemini_tts(spec: GenSpec, route: str) -> GenResult:
    t0 = time.time()
    model = settings.GEMINI_TTS_MODEL or TTS_MODEL_DEFAULT
    voice = spec.params.get("voice", "Kore")
    try:
        out = _paced_post(model, {
            "contents": [{"parts": [{"text": spec.prompt}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}},
                },
            },
        })
        for part in _inline_parts(out):
            blob = part.get("inline_data") or part.get("inlineData")
            if blob and blob.get("mime_type", blob.get("mimeType", "")).startswith("audio/"):
                pcm = base64.b64decode(blob["data"])
                rate = 24000
                mime = blob.get("mime_type", blob.get("mimeType", ""))
                if "rate=" in mime:
                    try:
                        rate = int(mime.split("rate=")[1].split(";")[0])
                    except ValueError:
                        pass
                return GenResult(
                    data=_pcm_to_wav(pcm, rate), ext="wav",
                    provider=route, model=model,
                    cost_usd=0.0,
                    latency_ms=int((time.time() - t0) * 1000),
                    params_used={**spec.params, "voice": voice, "model": model},
                )
        raise ProviderError("gemini: response contained no audio part")
    except httpx.HTTPError as e:
        raise ProviderError(f"gemini: {e}") from e
