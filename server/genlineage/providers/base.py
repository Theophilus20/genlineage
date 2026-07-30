from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class GenSpec:
    """One generation step, provider-agnostic."""

    modality: str  # image | video | audio | voice
    prompt: str
    params: dict = field(default_factory=dict)
    seed: int | None = None
    # source assets for img2vid / remix steps: list of sha256 digests
    inputs: list[str] = field(default_factory=list)


@dataclass
class GenResult:
    data: bytes
    ext: str  # png / gif / mp4 / wav / mp3
    provider: str  # "fal:flux-pro"
    model: str
    cost_usd: float
    latency_ms: int
    params_used: dict


class ProviderError(Exception):
    """Raised on provider failure → triggers failover to next route."""


class Generator(Protocol):
    def generate(self, spec: GenSpec) -> GenResult: ...
