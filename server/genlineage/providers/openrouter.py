"""OpenRouter video generation (async jobs API).

One normalized API over Veo 3.1 (Lite), Wan 2.6/2.7, Grok Imagine, Sora 2,
Kling, Seedance and more:

    POST /api/v1/videos            -> job {id, status, polling_url}
    GET  /api/v1/videos/{id}       -> poll until completed/failed
    GET  unsigned_urls[0]          -> MP4 bytes (bearer token required)

We use image-to-video when the step has a parent storyboard frame
(frame_images = first frame), and request native audio so the final cut
actually carries the soundtrack. Model is configurable — the default,
google/veo-3.1-lite, is the cheapest with audio.
"""
from __future__ import annotations

import time

import httpx

from ..config import settings
from .base import GenResult, GenSpec, ProviderError

API = "https://openrouter.ai/api/v1"
POLL_EVERY = 5
DEADLINE = 8 * 60  # video jobs take minutes


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}


def openrouter_video(spec: GenSpec, route: str) -> GenResult:
    t0 = time.time()
    model = settings.OPENROUTER_VIDEO_MODEL

    body: dict = {
        "model": model,
        "prompt": spec.prompt,
        "resolution": settings.OPENROUTER_VIDEO_RESOLUTION,
        "aspect_ratio": "16:9",
        "generate_audio": False,  # soundtrack comes from voiceover+music bed
    }
    dur = spec.params.get("duration") or settings.OPENROUTER_VIDEO_DURATION
    if dur:
        body["duration"] = int(dur)
    # image-to-video: animate the parent storyboard frame when we have one
    frame_b64 = spec.params.get("frame_image_b64")
    if frame_b64:
        mime = spec.params.get("frame_image_mime", "image/png")
        body["frame_images"] = [{
            "type": "image_url",
            "frame_type": "first_frame",
            "image_url": {"url": f"data:{mime};base64,{frame_b64}"},
        }]

    try:
        r = httpx.post(f"{API}/videos", json=body, headers=_headers(),
                       timeout=60)
        if r.status_code in (401, 403):
            raise ProviderError("openrouter: invalid API key")
        if r.status_code == 402:
            raise ProviderError("openrouter: out of credits — top up at openrouter.ai")
        if r.status_code >= 400:
            raise ProviderError(f"openrouter: HTTP {r.status_code}: {r.text[:200]}")
        job = r.json()
        job_id = job.get("id")
        if not job_id:
            raise ProviderError(f"openrouter: no job id in response: {r.text[:200]}")

        deadline = time.time() + DEADLINE
        status = job.get("status", "queued")
        while status not in {"completed", "failed", "cancelled", "expired"}:
            if time.time() > deadline:
                raise ProviderError("openrouter: video job timed out")
            time.sleep(POLL_EVERY)
            pr = httpx.get(f"{API}/videos/{job_id}", headers=_headers(),
                           timeout=30)
            pr.raise_for_status()
            job = pr.json()
            status = job.get("status")

        if status != "completed":
            raise ProviderError(
                f"openrouter: video {status}: {job.get('error') or 'no detail'}")

        urls = job.get("unsigned_urls") or []
        url = urls[0] if urls else f"{API}/videos/{job_id}/content?index=0"
        dl = httpx.get(url, headers=_headers(), timeout=120,
                       follow_redirects=True)
        dl.raise_for_status()
        ctype = dl.headers.get("content-type", "video/mp4")
        ext = "webm" if "webm" in ctype else "mp4"

        cost = float((job.get("usage") or {}).get("cost") or 0.0)
        params_used = {k: v for k, v in spec.params.items()
                       if k not in ("frame_image_b64", "frame_image_mime")}
        return GenResult(
            data=dl.content, ext=ext, provider=model, model=model,
            cost_usd=cost or 0.15,
            latency_ms=int((time.time() - t0) * 1000),
            params_used={**params_used, "model": model,
                         "resolution": body["resolution"],
                         "audio": True},
        )
    except httpx.HTTPError as e:
        raise ProviderError(f"openrouter: {e}") from e
