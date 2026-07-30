"""Mock providers for keyless local dev.

These synthesize *real* viewable assets — seeded generative-art PNGs,
animated GIF "video", sine-composition WAV audio — so the full pipeline
(hashing, dedup, eval gate, retry, failover, signing, DAG) runs end-to-end
offline.

The image renderer follows generative-art practice: colors organized along
a gradient axis, large soft radial glows layered like colored light, one
sharp focal accent for contrast, and fine grain to kill banding.

Determinism: same (prompt, seed, params) → byte-identical output, which is
what makes the branch-and-dedup demo work ("swap coffee → matcha: only
changed nodes regenerate").
"""
from __future__ import annotations

import hashlib
import io
import math
import random
import struct
import time
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .base import GenResult, GenSpec

# curated 5-stop palettes, deep base → light air (RGB)
_PALETTES = [
    # dusk
    [(24, 22, 52), (72, 48, 110), (168, 92, 130), (238, 150, 120), (250, 224, 196)],
    # forest
    [(12, 32, 26), (28, 74, 56), (92, 138, 100), (182, 204, 158), (240, 240, 220)],
    # ocean
    [(10, 24, 46), (22, 62, 100), (52, 122, 150), (140, 194, 196), (236, 242, 232)],
    # ember
    [(30, 18, 16), (92, 40, 28), (178, 84, 40), (232, 152, 72), (248, 222, 178)],
    # berry
    [(38, 16, 40), (94, 34, 84), (164, 72, 122), (222, 138, 158), (248, 220, 222)],
    # slate
    [(16, 18, 24), (46, 54, 68), (98, 112, 130), (168, 182, 194), (236, 240, 242)],
    # matcha
    [(20, 34, 22), (58, 88, 52), (120, 150, 92), (186, 202, 140), (244, 244, 224)],
    # espresso
    [(26, 18, 14), (70, 46, 32), (128, 90, 58), (190, 152, 108), (244, 230, 208)],
]


def _rng(spec: GenSpec, salt: str = "") -> random.Random:
    seed_material = f"{spec.prompt}|{spec.seed}|{sorted(spec.params.items())}|{salt}"
    return random.Random(hashlib.sha256(seed_material.encode()).hexdigest())


def _np_seed(spec: GenSpec, salt: str = "") -> np.random.RandomState:
    seed_material = f"{spec.prompt}|{spec.seed}|{sorted(spec.params.items())}|{salt}"
    h = hashlib.sha256(seed_material.encode()).digest()
    return np.random.RandomState(int.from_bytes(h[:4], "big"))


def _gradient_field(size: int, colors: list, angle: float) -> np.ndarray:
    """Multi-stop linear gradient across a seeded axis (float array HxWx3)."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64) / size
    u = (xx * math.cos(angle) + yy * math.sin(angle))
    u = (u - u.min()) / (u.max() - u.min() + 1e-9)
    stops = np.linspace(0, 1, len(colors))
    arr = np.zeros((size, size, 3))
    cols = np.array(colors, dtype=np.float64)
    for c in range(3):
        arr[..., c] = np.interp(u, stops, cols[:, c])
    return arr


def _glow(arr: np.ndarray, cx: float, cy: float, radius: float,
          color, strength: float) -> None:
    """Soft radial light, screen-blended in place."""
    size = arr.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    w = np.exp(-d2 / (2 * radius * radius))[..., None] * strength
    c = np.array(color, dtype=np.float64)
    arr[:] = 255 - (255 - arr) * (1 - w * (c / 255))  # screen blend


def _render_frame(spec: GenSpec, size: int, t: float,
                  palette: list, ss: int = 2) -> Image.Image:
    rng = _rng(spec, "compose")
    # ss=2 supersampling for stills; video frames pass ss=1 (4x faster)
    S = size * ss

    # 1 — atmospheric gradient base along a seeded axis
    angle = rng.uniform(0.7, 2.4) + 0.28 * math.sin(t * 1.1)  # slow light sweep
    base = _gradient_field(S, palette, angle)

    # 2 — large soft glows: colored light, drifting slowly with t
    for i in range(rng.randint(2, 4)):
        gx = (rng.uniform(0.1, 0.9) + 0.16 * math.sin(t * 1.6 + i * 2.1)) * S
        gy = (rng.uniform(0.1, 0.9) + 0.16 * math.cos(t * 1.3 + i * 1.7)) * S
        _glow(base, gx, gy, rng.uniform(0.22, 0.42) * S * (1 + 0.18 * math.sin(t * 2.4 + i)),
              palette[rng.randint(2, 4)],
              rng.uniform(0.35, 0.6) * (1 + 0.25 * math.sin(t * 1.9 + i * 2)))

    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(img, "RGBA")

    mode = rng.choice(["waves", "arcs", "orbs", "beams"])

    if mode == "waves":
        # layered sine ridges, colors darkening toward the bottom
        for k in range(4):
            depth = k / 3.0
            col = palette[1 + min(k, 2)]
            amp = S * rng.uniform(0.02, 0.06)
            freq = rng.uniform(1.2, 2.6)
            phase = rng.uniform(0, 6.28) + t * (2.2 + 0.8 * k)
            baseline = S * (0.45 + 0.16 * k)
            pts = [(x, baseline + amp * math.sin(freq * 6.28 * x / S + phase))
                   for x in range(0, S + 16, 16)]
            draw.polygon(pts + [(S, S), (0, S)], fill=col + (200,))
    elif mode == "arcs":
        cx = S * rng.uniform(0.3, 0.7)
        cy = S * rng.uniform(0.55, 0.95)
        for k in range(5, 0, -1):
            r = S * 0.14 * k * rng.uniform(0.9, 1.05)
            col = palette[(k % 4) + 1]
            draw.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 360,
                          fill=col + (235,))
    elif mode == "orbs":
        for _ in range(rng.randint(5, 8)):
            r = S * rng.uniform(0.07, 0.22)
            ox = rng.uniform(r, S - r) + 26 * ss * math.sin(t * 2.2 + r)
            oy = rng.uniform(r, S - r) + 26 * ss * math.cos(t * 1.7 + r)
            col = palette[rng.randint(1, 4)]
            draw.ellipse([ox - r, oy - r, ox + r, oy + r], fill=col + (150,))
    else:  # beams
        for _ in range(rng.randint(3, 5)):
            w = S * rng.uniform(0.06, 0.16)
            x0 = rng.uniform(-0.2, 1.0) * S + t * 46 * ss
            slope = S * rng.uniform(0.3, 0.9) * rng.choice([-1, 1])
            col = palette[rng.randint(1, 4)]
            draw.polygon([(x0, S), (x0 + slope, 0), (x0 + slope + w, 0),
                          (x0 + w, S)], fill=col + (110,))

    # 3 — one sharp focal accent against the soft field
    ax = S * rng.uniform(0.55, 0.85)
    ay = S * rng.uniform(0.12, 0.4)
    ar = S * rng.uniform(0.035, 0.06) * (1 + 0.22 * math.sin(t * 3.1))
    accent = palette[4]
    if rng.random() < 0.5:
        draw.ellipse([ax - ar, ay - ar, ax + ar, ay + ar], fill=accent + (255,))
    else:
        draw.ellipse([ax - ar, ay - ar, ax + ar, ay + ar],
                     outline=accent + (255,), width=max(2, int(ar * 0.28)))

    # downsample for antialiasing, then fine grain to kill banding
    img = img.resize((size, size), Image.LANCZOS)
    arr = np.asarray(img).astype(np.int16)
    grain = _np_seed(spec, f"grain{t:.3f}").normal(0, 5.0, arr.shape)
    return Image.fromarray(np.clip(arr + grain, 0, 255).astype(np.uint8))


class MockImage:
    name = "mock:procedural-image"

    def generate(self, spec: GenSpec) -> GenResult:
        t0 = time.time()
        rng = _rng(spec)
        custom = spec.params.get("palette")
        palette = ([tuple(c) for c in custom] if custom
                   else _PALETTES[rng.randint(0, len(_PALETTES) - 1)])
        size = int(spec.params.get("size", 512))
        img = _render_frame(spec, size, t=0.0, palette=palette)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return GenResult(
            data=buf.getvalue(), ext="png",
            provider=spec.params.get("as_provider", self.name),
            model="procedural-v1", cost_usd=0.0,
            latency_ms=int((time.time() - t0) * 1000), params_used=dict(spec.params),
        )


class MockVideo:
    name = "mock:procedural-video"

    def generate(self, spec: GenSpec) -> GenResult:
        t0 = time.time()
        rng = _rng(spec)
        custom = spec.params.get("palette")
        palette = ([tuple(c) for c in custom] if custom
                   else _PALETTES[rng.randint(0, len(_PALETTES) - 1)])
        size = int(spec.params.get("size", 320))
        frames = [
            _render_frame(spec, size, t=k / 4.0, palette=palette, ss=1)
            for k in range(int(spec.params.get("frames", 16)))
        ]
        buf = io.BytesIO()
        frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                       duration=125, loop=0)
        return GenResult(
            data=buf.getvalue(), ext="gif",
            provider=spec.params.get("as_provider", self.name),
            model="procedural-video-v1", cost_usd=0.0,
            latency_ms=int((time.time() - t0) * 1000), params_used=dict(spec.params),
        )


class MockAudio:
    name = "mock:procedural-audio"

    def generate(self, spec: GenSpec) -> GenResult:
        t0 = time.time()
        rng = _rng(spec)
        sr, secs = 22050, float(spec.params.get("seconds", 3.0))
        # seeded chord progression
        base = rng.choice([220.0, 246.9, 261.6, 293.7])
        ratios = [1.0, 1.25, 1.5, rng.choice([1.875, 2.0])]
        n = int(sr * secs)
        samples = bytearray()
        for i in range(n):
            t = i / sr
            step = int(t * 2) % len(ratios)
            f = base * ratios[step]
            env = 0.5 * (1 - abs((t * 2 % 1) - 0.5) * 2) + 0.1
            v = env * (math.sin(2 * math.pi * f * t)
                       + 0.3 * math.sin(2 * math.pi * f * 2 * t))
            samples += struct.pack("<h", int(max(-1, min(1, v * 0.6)) * 32767))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(bytes(samples))
        return GenResult(
            data=buf.getvalue(), ext="wav",
            provider=spec.params.get("as_provider", self.name),
            model="procedural-audio-v1", cost_usd=0.0,
            latency_ms=int((time.time() - t0) * 1000), params_used=dict(spec.params),
        )


MOCKS = {"image": MockImage(), "video": MockVideo(),
         "audio": MockAudio(), "voice": MockAudio()}
