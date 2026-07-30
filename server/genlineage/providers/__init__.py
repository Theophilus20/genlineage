"""Provider routing — the Genblaze layer.

One abstraction over fal.ai + Replicate + ElevenLabs. Each modality has a
failover chain; a ProviderError (or a failed quality gate exhausting its
retries) advances to the next provider in the chain with the same spec.

With no API keys, every route resolves to a mock generator that produces
real seeded assets, labeled `as_provider` so the DAG/demo reads identically.
"""
from __future__ import annotations

import time

import httpx

from ..config import settings
from .base import GenResult, GenSpec, ProviderError
from .mock import MOCKS

# Paid providers first; Gemini (free tier) as the live fallback; mock last.
ROUTES: dict[str, list[str]] = {
    "image": ["fal:flux-pro", "replicate:sdxl", "gemini:flash-image"],
    "video": ["openrouter:video", "fal:kling-v2", "fal:hailuo", "replicate:svd"],
    "audio": ["fal:musicgen"],
    "voice": ["elevenlabs:tts", "gemini:tts", "fal:tts"],
}

# indicative pricing for cost accounting in live mode
PRICE = {"fal:flux-pro": 0.05, "replicate:sdxl": 0.04, "fal:kling-v2": 0.35,
         "fal:hailuo": 0.30, "replicate:svd": 0.25, "fal:musicgen": 0.03,
         "elevenlabs:tts": 0.02, "fal:tts": 0.02,
         "gemini:flash-image": 0.0, "gemini:tts": 0.0,  # personal free tier
         "openrouter:video": 0.15}

FAL_MODELS = {"flux-pro": "fal-ai/flux-pro/v1.1", "kling-v2": "fal-ai/kling-video/v2/master/text-to-video",
              "hailuo": "fal-ai/minimax-video-01", "musicgen": "fal-ai/musicgen",
              "tts": "fal-ai/playai/tts/v3"}


def _download(url: str) -> tuple[bytes, str]:
    r = httpx.get(url, timeout=120, follow_redirects=True)
    r.raise_for_status()
    ext = url.rsplit("?", 1)[0].rsplit(".", 1)[-1].lower()
    if ext not in {"png", "jpg", "jpeg", "webp", "gif", "mp4", "webm", "wav", "mp3"}:
        ext = {"image": "png", "video": "mp4", "audio": "mp3"}.get(
            r.headers.get("content-type", "").split("/")[0], "bin")
    return r.content, ext


def _fal(model_slug: str, spec: GenSpec, route: str) -> GenResult:
    """fal.ai queue API: submit → poll → download."""
    t0 = time.time()
    model = FAL_MODELS.get(model_slug, model_slug)
    headers = {"Authorization": f"Key {settings.FAL_KEY}"}
    payload = {"prompt": spec.prompt, **spec.params}
    if spec.seed is not None:
        payload["seed"] = spec.seed
    try:
        sub = httpx.post(f"https://queue.fal.run/{model}", json=payload,
                         headers=headers, timeout=30)
        sub.raise_for_status()
        status_url = sub.json()["status_url"]
        response_url = sub.json()["response_url"]
        deadline = time.time() + 300
        while time.time() < deadline:
            st = httpx.get(status_url, headers=headers, timeout=30).json()
            if st.get("status") == "COMPLETED":
                out = httpx.get(response_url, headers=headers, timeout=30).json()
                media = (out.get("images") or [out.get("video") or out.get("audio") or {}])[0]
                data, ext = _download(media["url"])
                return GenResult(data=data, ext=ext, provider=route, model=model,
                                 cost_usd=PRICE.get(route, 0.05),
                                 latency_ms=int((time.time() - t0) * 1000),
                                 params_used=payload)
            if st.get("status") in {"FAILED", "CANCELLED"}:
                raise ProviderError(f"fal status {st.get('status')}")
            time.sleep(2)
        raise ProviderError("fal timeout")
    except (httpx.HTTPError, KeyError) as e:
        raise ProviderError(f"fal: {e}") from e


_replicate_versions: dict[str, str] = {}


def _replicate_version(model: str, headers: dict) -> str:
    """Community models need a version id — resolve and cache the latest."""
    if model not in _replicate_versions:
        r = httpx.get(f"https://api.replicate.com/v1/models/{model}",
                      headers=headers, timeout=30)
        r.raise_for_status()
        _replicate_versions[model] = r.json()["latest_version"]["id"]
    return _replicate_versions[model]


def _replicate(model_slug: str, spec: GenSpec, route: str) -> GenResult:
    t0 = time.time()
    models = {"sdxl": "stability-ai/sdxl",
              "svd": "stability-ai/stable-video-diffusion"}
    model = models.get(model_slug, model_slug)
    headers = {"Authorization": f"Bearer {settings.REPLICATE_API_TOKEN}",
               "Prefer": "wait=60"}
    try:
        version = _replicate_version(model, headers)
        if model_slug == "svd":
            # SVD is image-to-video only — it takes an input_image, no prompt
            frame_b64 = spec.params.get("frame_image_b64")
            if not frame_b64:
                raise ProviderError("replicate svd: needs a parent frame image")
            mime = spec.params.get("frame_image_mime", "image/png")
            inputs = {"input_image": f"data:{mime};base64,{frame_b64}"}
        else:
            inputs = {"prompt": spec.prompt,
                      "disable_safety_checker": True,  # false NSFW on product shots
                      **{k: v for k, v in spec.params.items()
                         if k not in ("frame_image_b64", "frame_image_mime",
                                      "palette")}}
        r = httpx.post("https://api.replicate.com/v1/predictions",
                       json={"version": version, "input": inputs},
                       headers=headers, timeout=120)
        r.raise_for_status()
        pred = r.json()
        deadline = time.time() + 300
        while pred.get("status") not in {"succeeded", "failed", "canceled"}:
            if time.time() > deadline:
                raise ProviderError("replicate timeout")
            time.sleep(2)
            pred = httpx.get(pred["urls"]["get"], headers=headers,
                             timeout=30).json()
        if pred["status"] != "succeeded":
            raise ProviderError(f"replicate: {pred.get('error') or pred['status']}")
        out = pred.get("output")
        url = out[0] if isinstance(out, list) else out
        data, ext = _download(url)
        return GenResult(data=data, ext=ext, provider=route, model=model,
                         cost_usd=PRICE.get(route, 0.05),
                         latency_ms=int((time.time() - t0) * 1000),
                         params_used=dict(spec.params))
    except (httpx.HTTPError, KeyError, TypeError, IndexError) as e:
        raise ProviderError(f"replicate: {e}") from e


# voice choice -> ElevenLabs voice ids (Rachel female, Adam male)
_EL_VOICES = {"Kore": "21m00Tcm4TlvDq8ikWAM", "Leda": "21m00Tcm4TlvDq8ikWAM",
              "Charon": "pNInz6obpgDQGcFmaJgB", "Puck": "pNInz6obpgDQGcFmaJgB"}


def _elevenlabs(_slug: str, spec: GenSpec, route: str) -> GenResult:
    t0 = time.time()
    voice = spec.params.get("voice_id") or _EL_VOICES.get(
        spec.params.get("voice"), "21m00Tcm4TlvDq8ikWAM")
    try:
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            json={"text": spec.prompt, "model_id": "eleven_multilingual_v2"},
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY}, timeout=120)
        r.raise_for_status()
        return GenResult(data=r.content, ext="mp3", provider=route, model="eleven_multilingual_v2",
                         cost_usd=PRICE.get(route, 0.02),
                         latency_ms=int((time.time() - t0) * 1000),
                         params_used=dict(spec.params))
    except httpx.HTTPError as e:
        raise ProviderError(f"elevenlabs: {e}") from e


from .gemini import gemini_image, gemini_tts
from .openrouter import openrouter_video


def _gemini(model_slug: str, spec: GenSpec, route: str) -> GenResult:
    if model_slug == "tts":
        return gemini_tts(spec, route)
    return gemini_image(spec, route)


def _openrouter(model_slug: str, spec: GenSpec, route: str) -> GenResult:
    return openrouter_video(spec, route)


_LIVE = {"fal": _fal, "replicate": _replicate, "elevenlabs": _elevenlabs,
         "gemini": _gemini, "openrouter": _openrouter}


def generate(route: str, spec: GenSpec) -> GenResult:
    """Run one generation on one route ('fal:flux-pro'), live or mock."""
    vendor, _, model_slug = route.partition(":")
    if settings.provider_is_live(vendor):
        return _LIVE[vendor](model_slug, spec, route)
    mock = MOCKS[spec.modality]
    result = mock.generate(spec)
    result.provider = "mock (no API key)"  # never impersonate a live provider
    result.model = f"mock-{spec.modality}"
    result.cost_usd = 0.0
    return result


def generate_mock(spec: GenSpec) -> GenResult:
    """Last-resort generator when every live provider has failed — the
    pipeline must degrade, never die."""
    result = MOCKS[spec.modality].generate(spec)
    result.provider = "mock (live providers unavailable)"
    result.model = f"mock-{spec.modality}"
    result.cost_usd = 0.0
    return result


def routes_for(modality: str) -> list[str]:
    """The failover chain for a modality, restricted to vendors that are
    actually live. If none are live, return the full chain so the first
    route resolves to the mock generator (honestly labeled)."""
    chain = list(ROUTES.get(modality, ROUTES["image"]))
    live = [r for r in chain if settings.provider_is_live(r.partition(":")[0])]
    return live or chain
