"""① PLAN — decompose a brief into pipeline steps.

Live: Gemini (AI Studio free tier) returns a JSON step list.
Mock: a heuristic that produces the canonical demo pipeline
      (script → frames → shots → voiceover → final cut).
"""
from __future__ import annotations

import json

import httpx

from ..config import settings

PLAN_PROMPT = """You are a media pipeline planner. Decompose the brief into
generation steps. Respond ONLY with JSON: a list of objects with keys:
id (short slug), modality (image|video|audio|voice), prompt (full generation
prompt), depends_on (list of step ids), params (object, may be empty).
Brief: {brief}"""


def _gemini_plan(brief: str) -> list[dict]:
    r = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={"key": settings.GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": PLAN_PROMPT.format(brief=brief)}]}]},
        timeout=60,
    )
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    return json.loads(text)


def _mock_plan(brief: str, n_shots: int = 2, video_secs=None) -> list[dict]:
    subject = brief.strip().rstrip(".")
    frames = [
        {"id": f"frame-{i+1}", "modality": "image", "depends_on": [],
         "prompt": (f"Professional advertising still for {subject}: {angle}. "
                    "Cinematic product photography, dramatic soft lighting, "
                    "shallow depth of field, rich color grading, premium "
                    "commercial aesthetic, ultra-detailed, no text or watermarks."),
         "params": {"size": 512}}
        for i, angle in enumerate(
            ["establishing shot", "close-up on product", "lifestyle moment",
             "logo reveal"][:max(2, min(int(n_shots or 2), 4))])
    ]
    shots = [
        {"id": f"shot-{i+1}", "modality": "video",
         "depends_on": [f"frame-{i+1}"],
         "prompt": (f"Cinematic commercial shot for {subject}: bring this scene "
                    "to life with a smooth slow dolly camera movement, film-grade "
                    "lighting, elegant motion in the details, premium advertising look."),
         "params": {"frames": 16, "size": 320,
                    **({"duration": int(video_secs)} if video_secs else {})}}
        for i in range(max(2, min(int(n_shots or 2), 4)))
    ]
    return [
        *frames,
        *shots,
        {"id": "voiceover", "modality": "voice", "depends_on": [],
         # this text is SPOKEN literally by the TTS voice

         "prompt": f"Meet {subject}. Crafted with care, made for you. {subject} — available now.",
         "params": {"seconds": 3}},
        # subject-independent steps: identical recipes across remixes, so a
        # branch that only changes the subject dedup-references these
        {"id": "music-bed", "modality": "audio", "depends_on": [],
         "prompt": "Warm lo-fi instrumental bed, 30 seconds, no vocals, gentle build",
         "params": {"seconds": 3}},
        {"id": "grain-pass", "modality": "image", "depends_on": [],
         "prompt": "Subtle 35mm film grain overlay texture, neutral gray, tileable",
         "params": {"size": 512}},
        {"id": "final-cut", "modality": "video",
         "depends_on": [s["id"] for s in shots] + [f["id"] for f in frames[2:]]
                        + ["voiceover", "music-bed", "grain-pass"],
         "prompt": f"Polished 30-second commercial for {subject}: cinematic pacing, seamless transitions between hero shots, warm color grade, premium brand energy, ends on the product with a clean beauty shot.",
         "params": {"frames": 24, "size": 320}},
    ]


def plan(brief: str, n_shots: int = 2, video_secs=None) -> list[dict]:
    if settings.provider_is_live("gemini"):
        try:
            steps = _gemini_plan(brief)
            if isinstance(steps, list) and steps:
                return steps
        except Exception:
            pass  # planner failure should never kill a job — fall back
    return _mock_plan(brief, n_shots=n_shots, video_secs=video_secs)
