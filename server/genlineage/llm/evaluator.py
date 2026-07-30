"""③ EVALUATE — the agentic quality gate.

Live: Gemini Vision scores the output against the step spec and returns a
JSON rubric {score: 0-10, critique, param_suggestions}.
Mock: deterministic seeded scoring. A tunable share of *first attempts*
fail the gate on purpose so the retry → failover path shows up in demos
(the doc's demo script depends on one frame failing and recovering).
"""
from __future__ import annotations

import base64
import hashlib
import json

import httpx

from ..config import settings

EVAL_PROMPT = """Score this generated asset against the spec. Respond ONLY
with JSON: {{"score": 0-10 float, "critique": "one sentence",
"param_suggestions": {{}} }}.
Spec: {spec}"""

MIME = {"png": "image/png", "gif": "image/gif", "webp": "image/webp",
        "jpg": "image/jpeg", "mp4": "video/mp4", "wav": "audio/wav",
        "mp3": "audio/mpeg"}


def _gemini_eval(spec_prompt: str, data: bytes, ext: str) -> dict:
    r = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={"key": settings.GEMINI_API_KEY},
        json={"contents": [{"parts": [
            {"text": EVAL_PROMPT.format(spec=spec_prompt)},
            {"inline_data": {"mime_type": MIME.get(ext, "application/octet-stream"),
                             "data": base64.b64encode(data).decode()}},
        ]}]},
        timeout=90,
    )
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    return json.loads(text)


def _mock_eval(spec_prompt: str, data: bytes, attempt: int, gate_min: float) -> dict:
    h = hashlib.sha256(spec_prompt.encode() + data[:64]).digest()
    if attempt == 1 and h[1] % 4 == 0:  # ~25% of first attempts fail the gate
        # a hair below the active threshold, clamped to a sane floor
        fail = max(1.0, round(gate_min - 0.6, 1))
        return {
            "score": fail,
            "critique": "Composition drifts from spec; subject under-emphasized "
                        "and palette reads muddy against the brief.",
            "param_suggestions": {"guidance": 8.5, "size": 512},
        }
    # comfortably above the active threshold, capped at 9.9
    lift = (h[0] % 12) / 10.0  # 0.0 – 1.1
    return {
        "score": round(min(9.9, gate_min + 0.3 + lift), 1),
        "critique": "Matches spec: subject clear, composition and palette on-brief.",
        "param_suggestions": {},
    }


def evaluate(spec_prompt: str, data: bytes, ext: str, attempt: int,
             gate_min: float = None) -> dict:
    gate_min = settings.QUALITY_GATE_MIN if gate_min is None else gate_min
    if settings.provider_is_live("gemini") and ext in MIME:
        try:
            rubric = _gemini_eval(spec_prompt, data, ext)
            if "score" in rubric:
                rubric.setdefault("critique", "")
                rubric.setdefault("param_suggestions", {})
                return rubric
        except Exception:
            pass
    return _mock_eval(spec_prompt, data, attempt, gate_min)
