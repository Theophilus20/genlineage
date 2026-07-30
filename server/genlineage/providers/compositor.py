"""Final-cut compositor: real assembly, not another generation.

Concatenates the shot videos in plan order, lays the voiceover on top, and
ducks the music bed underneath — producing a single MP4 whose provenance
recipe lists exactly which commits it was cut from. Uses the static ffmpeg
binary bundled by imageio-ffmpeg (works on Windows/macOS/Linux, no system
install needed).
"""
from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from .base import GenResult, GenSpec, ProviderError


def _ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # pragma: no cover
        raise ProviderError(f"compositor: ffmpeg unavailable ({e}) — "
                            "pip install imageio-ffmpeg") from e


def _duration(ff: str, path) -> float:
    """Parse 'Duration: HH:MM:SS.cc' from ffmpeg -i (no ffprobe in the bundle)."""
    import re
    proc = subprocess.run([ff, "-i", str(path)], capture_output=True)
    m = re.search(rb"Duration: (\d+):(\d+):(\d+\.\d+)", proc.stderr)
    if not m:
        return 0.0
    h, mnt, sec = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mnt * 60 + sec


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        tail = proc.stderr.decode(errors="replace")[-400:]
        raise ProviderError(f"compositor: ffmpeg failed: {tail}")


def compose_final(spec: GenSpec, route: str) -> GenResult:
    """spec.params['_media'] = {'shots': [(bytes, ext)...],
    'voiceover': (bytes, ext)|None, 'music': (bytes, ext)|None}"""
    t0 = time.time()
    media = spec.params.get("_media") or {}
    shots = media.get("shots") or []
    if not shots:
        raise ProviderError("compositor: no shot videos to assemble")
    voice = media.get("voiceover")
    music = media.get("music")
    grain = media.get("grain")  # (bytes, ext) still image, blended on top

    ff = _ffmpeg()
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)

        # 1 — normalize every shot to the same codec/size (gif or mp4 in)
        norm = []
        for i, (data, ext) in enumerate(shots):
            src = tdir / f"shot{i}.{ext}"
            src.write_bytes(data)
            dst = tdir / f"norm{i}.mp4"
            try:
                _run([ff, "-y", "-i", str(src),
                      "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                             "pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p",
                      "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                      str(dst)])
                norm.append(dst)
            except ProviderError:
                continue  # one bad shot must not sink the whole cut
        if not norm:
            raise ProviderError("compositor: no shot could be decoded")

        # 2 — concat the normalized shots
        video = tdir / "video.mp4"
        durs = [_duration(ff, p) or 2.0 for p in norm]
        XF = 0.5  # crossfade seconds
        if len(norm) == 1:
            total = durs[0]
            _run([ff, "-y", "-i", str(norm[0]),
                  "-vf", f"fade=t=in:d=0.5,fade=t=out:st={max(0.1, total-0.6):.2f}:d=0.6",
                  "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", str(video)])
        else:
            ins, fc, cur, off = [], [], "[0:v]", 0.0
            for p in norm:
                ins += ["-i", str(p)]
            for i in range(1, len(norm)):
                off += durs[i - 1] - XF
                nxt = f"[x{i}]"
                fc.append(f"{cur}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.2f}{nxt}")
                cur = nxt
            total = sum(durs) - XF * (len(norm) - 1)
            fc.append(f"{cur}fade=t=in:d=0.5,fade=t=out:st={max(0.1, total-0.6):.2f}:d=0.6[vout]")
            _run([ff, "-y", *ins, "-filter_complex", ";".join(fc),
                  "-map", "[vout]", "-c:v", "libx264", "-preset", "veryfast",
                  "-crf", "23", str(video)])

        # 2b — blend the grain pass over the whole cut (subtle film texture)
        if grain:
            gpath = tdir / f"grain.{grain[1]}"
            gpath.write_bytes(grain[0])
            grained = tdir / "video-grain.mp4"
            dur = _duration(ff, video) or 1.0
            _run([ff, "-y", "-i", str(video),
                  "-loop", "1", "-t", f"{dur:.2f}", "-i", str(gpath),
                  "-filter_complex",
                  "[1:v]scale=1280:720,format=yuv420p[g];"
                  "[0:v][g]blend=all_mode=overlay:all_opacity=0.12[v]",
                  "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast",
                  "-crf", "23", "-shortest", str(grained)])
            video = grained

        # 3 — soundtrack: voiceover on top, music ducked underneath
        out = tdir / "final.mp4"
        audio_inputs, filters, mix = [], [], []
        idx = 1
        if voice:
            vpath = tdir / f"voice.{voice[1]}"
            vpath.write_bytes(voice[0])
            audio_inputs += ["-i", str(vpath)]
            filters.append(f"[{idx}:a]aresample=44100,volume=1.0[vo]")
            mix.append("[vo]")
            idx += 1
        if music:
            mpath = tdir / f"music.{music[1]}"
            mpath.write_bytes(music[0])
            audio_inputs += ["-stream_loop", "-1", "-i", str(mpath)]
            filters.append(f"[{idx}:a]aresample=44100,volume=0.35[mu]")
            mix.append("[mu]")
            idx += 1

        if mix:
            fc = (";".join(filters) + ";" + "".join(mix)
                  + f"amix=inputs={len(mix)}:duration=longest:dropout_transition=2,"
                  + f"afade=t=in:d=0.4,afade=t=out:st={max(0.1, total-0.8):.2f}:d=0.8[aud]")
            _run([ff, "-y", "-i", str(video), *audio_inputs,
                  "-filter_complex", fc,
                  "-map", "0:v", "-map", "[aud]",
                  "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)])
        else:
            out = video

        data = out.read_bytes()

    return GenResult(
        data=data, ext="mp4", provider=route, model="ffmpeg-concat-mix",
        cost_usd=0.0, latency_ms=int((time.time() - t0) * 1000),
        params_used={"shots": len(shots), "grain": bool(grain),
                     "voiceover": bool(voice), "music": bool(music),
                     "transitions": "crossfade + fades", "soundtrack": "voiceover + ducked music"
                                   if voice and music else
                                   "voiceover" if voice else
                                   "music" if music else "silent"},
    )
