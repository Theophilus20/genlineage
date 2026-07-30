"""The five-phase pipeline worker.

① PLAN      brief → steps (Gemini or heuristic)
② GENERATE  Genblaze-style routing per modality
③ EVALUATE  quality gate: rubric score vs QUALITY_GATE_MIN
④ RETRY     revised params on same provider, then FAILOVER down the chain
⑤ COMMIT    hash → sign manifest → upload → append DAG log → index

Remixing: when a job carries a base_branch, steps whose prompt+params are
unchanged are not regenerated — the commit is dedup-referenced from the
content store and recorded with `reused_from`.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Callable

from ..config import settings
from ..llm.evaluator import evaluate
from ..llm.planner import plan
from ..models import Commit, Job, SessionLocal
from ..providers.compositor import compose_final
from ..providers import (GenSpec, ProviderError, generate, generate_mock,
                         routes_for)
from ..genblaze_bridge import build_manifest as build_genblaze_manifest
from ..signing import get_signing_key, sign_manifest


def _gb_sign(data: bytes) -> str:
    return get_signing_key().sign(data).signature.hex()
from ..storage import get_storage

Emit = Callable[[str, dict], None]


def _recipe_key(step: dict, input_hash: str | None = None) -> str:
    material = json.dumps(
        {"prompt": step["prompt"], "params": step.get("params", {}),
         "modality": step["modality"], "input": input_hash or ""}, sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()


def _palette_from_image(data: bytes) -> list | None:
    """Dominant 5-stop palette from an uploaded product image, dark → light."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data)).convert("RGB").resize((96, 96))
        q = img.quantize(colors=5, method=Image.MEDIANCUT).convert("RGB")
        colors = sorted({q.getpixel((x, y)) for x in range(0, 96, 7)
                         for y in range(0, 96, 7)},
                        key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
        while len(colors) < 5:
            colors.append(colors[-1])
        return [list(c) for c in colors[:5]]
    except Exception:
        return None


def run_job(job_id: str, emit: Emit) -> None:
    db = SessionLocal()
    storage = get_storage()
    job = db.get(Job, job_id)
    job.status = "running"
    db.commit()
    gate_min = job.gate_min if job.gate_min is not None else settings.QUALITY_GATE_MIN

    try:
        # ① PLAN ------------------------------------------------------------
        emit("plan.start", {"brief": job.brief})
        steps = plan(job.brief, n_shots=job.n_shots or 2,
                     video_secs=job.video_secs or None)
        emit("plan.done", {"steps": [{"id": s["id"], "modality": s["modality"],
                                      "depends_on": s.get("depends_on", [])}
                                     for s in steps]})

        # user-uploaded product image: root commit + palette for generation
        input_palette = None
        if job.input_hash and job.input_ext:
            raw = storage.get_asset(job.input_hash, job.input_ext)
            if raw:
                input_palette = _palette_from_image(raw)
                recipe = {"provider": "upload:user", "model": "user-input",
                          "prompt": "user-uploaded product image", "params": {},
                          "seed": None}
                claim = {"hash": job.input_hash, "parents": [], "branch": job.branch,
                         "recipe": recipe, "project": job.project_id,
                         "generator": "genlineage-upload/2.0"}
                manifest = sign_manifest(claim)
                storage.put_provenance(job.input_hash, "manifest.json",
                                       json.dumps(manifest, indent=2).encode())
                db.merge(Commit(hash=job.input_hash, project_id=job.project_id,
                                branch=job.branch, step_id="product-input",
                                modality="image", ext=job.input_ext, parents=[],
                                recipe=recipe, evals=[], cost_usd=0.0,
                                latency_ms=0, job_id=job.id,
                                manifest_sig=manifest["signature"]["sig"]))
                db.commit()
                storage.append_dag(job.project_id, json.dumps(
                    {"hash": job.input_hash, "branch": job.branch,
                     "step": "product-input", "modality": "image",
                     "ext": job.input_ext, "parents": [], "recipe": recipe,
                     "sig": manifest["signature"]["sig"]}))
                emit("step.commit", {"step": "product-input",
                                     "hash": job.input_hash,
                                     "provider": "upload:user", "score": None})

        # user-written voiceover: spoken verbatim; also folded into the final
        # cut prompt so live video models with native audio say it
        if job.voice_script:
            for st in steps:
                if st["id"] == "voiceover":
                    st["prompt"] = job.voice_script
                if st["id"] == "final-cut":
                    st["prompt"] += f' Voiceover says: "{job.voice_script}"'
        # voice choice flows to the TTS providers
        if job.voice:
            for st in steps:
                if st["id"] == "voiceover":
                    st.setdefault("params", {})["voice"] = job.voice
        # music: preset prompt, or drop the step entirely
        MUSIC_PRESETS = {
            "lofi": "Warm lo-fi instrumental bed, 30 seconds, no vocals, gentle build",
            "cinematic": "Uplifting cinematic orchestral bed, 30 seconds, swelling strings, no vocals",
            "ambient": "Minimal ambient pads, 30 seconds, calm and spacious, no vocals",
            "electronic": "Energetic modern electronic bed, 30 seconds, driving pulse, no vocals",
        }
        if job.music_style == "none":
            steps = [st for st in steps if st["id"] != "music-bed"]
            for st in steps:
                st["depends_on"] = [d for d in st.get("depends_on", [])
                                    if d != "music-bed"]
        elif job.music_style in MUSIC_PRESETS:
            for st in steps:
                if st["id"] == "music-bed":
                    st["prompt"] = MUSIC_PRESETS[job.music_style]

        # index prior commits on the base branch for dedup on remix
        base_commits: dict[str, Commit] = {}
        if job.base_branch:
            for c in (db.query(Commit)
                        .filter_by(project_id=job.project_id, branch=job.base_branch)
                        .all()):
                if c.recipe_key:
                    base_commits[c.recipe_key] = c

        produced: dict[str, str] = {}  # step id → commit hash
        total_cost = 0.0

        for step in steps:
            step_id = step["id"]
            seed = step.get("seed") or random.randint(1, 2**31)
            parents = [produced[d] for d in step.get("depends_on", []) if d in produced]
            # attach the product image only to root visual steps — descendants
            # inherit the lineage transitively, keeping the graph readable
            if (job.input_hash and step["modality"] in ("image", "video")
                    and not parents):
                parents = [job.input_hash]

            # dedup: identical recipe already on the base branch ------------
            reuse = base_commits.get(_recipe_key(step, job.input_hash))
            if reuse is not None:
                emit("step.reused", {"step": step_id, "hash": reuse.hash,
                                     "from_branch": job.base_branch})
                produced[step_id] = reuse.hash
                _index_reused(db, job, step, reuse, parents, storage)
                continue

            # ② GENERATE + ③ EVALUATE + ④ RETRY/FAILOVER --------------------
            spec = GenSpec(modality=step["modality"], prompt=step["prompt"],
                           params=dict(step.get("params", {})), seed=seed,
                           inputs=parents)
            if input_palette and step["modality"] in ("image", "video"):
                spec.params["palette"] = input_palette
            # video steps get their first parent FRAME for image-to-video
            if step["modality"] == "video":
                for parent_hash in parents:
                    pc = db.query(Commit).filter_by(hash=parent_hash).first()
                    if pc and pc.modality == "image":
                        try:
                            raw = storage.get_asset(pc.hash, pc.ext)
                            if raw:
                                import base64 as _b64
                                spec.params["frame_image_b64"] = _b64.b64encode(raw).decode()
                                spec.params["frame_image_mime"] = f"image/{'jpeg' if pc.ext=='jpg' else pc.ext}"
                        except Exception:
                            pass
                        break
            evals: list[dict] = []
            result = None
            attempt = 0

            # final-cut: assemble the ACTUAL shots + soundtrack first
            if step_id == "final-cut":
                media = {"shots": [], "voiceover": None, "music": None}
                for ph in parents:
                    pc = db.query(Commit).filter_by(hash=ph).first()
                    if not pc:
                        continue
                    try:
                        raw = storage.get_asset(pc.hash, pc.ext)
                    except Exception:
                        raw = None
                    if not raw:
                        continue
                    if pc.modality == "video":
                        media["shots"].append((raw, pc.ext))
                    elif pc.modality == "image":
                        media["grain"] = (raw, pc.ext)
                    elif pc.modality == "voice":
                        media["voiceover"] = (raw, pc.ext)
                    elif pc.modality == "audio":
                        media["music"] = (raw, pc.ext)
                if media["shots"]:
                    try:
                        cspec = GenSpec(modality="video", prompt=step["prompt"],
                                        params={"_media": media}, seed=seed,
                                        inputs=parents)
                        candidate = compose_final(cspec, "genlineage:compositor")
                        rubric = evaluate(step["prompt"], candidate.data,
                                          candidate.ext, 1, gate_min)
                        record = {"attempt": 1, "provider": candidate.provider,
                                  "score": rubric["score"],
                                  "critique": rubric["critique"], "cost_usd": 0.0}
                        evals.append(record)
                        emit("step.eval", {"step": step_id, **record})
                        result = candidate
                    except ProviderError as e:
                        emit("step.provider_error",
                             {"step": step_id, "provider": "genlineage:compositor",
                              "error": str(e)})

            for route in ([] if result else routes_for(step["modality"])):
                for _ in range(settings.MAX_ATTEMPTS_PER_PROVIDER):
                    attempt += 1
                    emit("step.generate", {"step": step_id, "provider": route,
                                           "attempt": attempt})
                    try:
                        candidate = generate(route, spec)
                    except ProviderError as e:
                        evals.append({"attempt": attempt, "provider": route,
                                      "score": None, "critique": f"provider error: {e}",
                                      "cost_usd": 0.0})
                        emit("step.provider_error", {"step": step_id,
                                                     "provider": route, "error": str(e)})
                        break  # failover to next provider in the chain

                    rubric = evaluate(step["prompt"], candidate.data,
                                      candidate.ext, attempt, gate_min)
                    total_cost += candidate.cost_usd
                    record = {"attempt": attempt, "provider": candidate.provider,
                              "score": rubric["score"], "critique": rubric["critique"],
                              "cost_usd": candidate.cost_usd}
                    evals.append(record)
                    emit("step.eval", {"step": step_id, **record})

                    if rubric["score"] >= gate_min:
                        result = candidate
                        break

                    # gate failed → keep the reject, fold critique into params
                    storage.put_failure(job.id, attempt, candidate.ext, candidate.data)
                    spec.params.update(rubric.get("param_suggestions", {}))
                    spec.seed = seed + attempt  # nudge
                    emit("step.retry", {"step": step_id,
                                        "revised_params": rubric.get("param_suggestions", {})})
                if result:
                    break

            if result is None:
                # every live route exhausted → degrade to mock, never die.
                # The commit is honestly labeled so provenance stays truthful.
                storage.put_failure(job.id, attempt,
                                    "json", json.dumps(evals).encode())
                emit("step.fallback", {
                    "step": step_id, "attempts": attempt,
                    "note": "all live providers failed — mock output committed"})
                result = generate_mock(spec)
                rubric = evaluate(step["prompt"], result.data, result.ext,
                                  attempt + 1, gate_min)
                record = {"attempt": attempt + 1, "provider": result.provider,
                          "score": rubric["score"], "critique": rubric["critique"],
                          "cost_usd": 0.0}
                evals.append(record)
                emit("step.eval", {"step": step_id, **record})

            # ⑤ COMMIT -------------------------------------------------------
            digest = storage.put_asset(result.data, result.ext)
            for _k in ("frame_image_b64", "frame_image_mime", "_media"):
                result.params_used.pop(_k, None)
            recipe = {"provider": result.provider, "model": result.model,
                      "prompt": step["prompt"], "params": result.params_used,
                      "seed": spec.seed}
            claim = {"hash": digest, "parents": parents, "branch": job.branch,
                     "recipe": recipe, "project": job.project_id,
                     "generator": "genlineage-pipeline/2.0"}
            manifest = sign_manifest(claim)
            storage.put_provenance(digest, "manifest.json",
                                   json.dumps(manifest, indent=2).encode())
            storage.put_provenance(digest, "eval_log.json",
                                   json.dumps(evals, indent=2).encode())

            # official Genblaze SDK manifest — second, interoperable
            # provenance record, signed with the same ed25519 key
            gb = build_genblaze_manifest(
                job_id=job.id, project_id=job.project_id, brief=job.brief,
                step_id=step_id, provider=result.provider, model=result.model,
                modality=step["modality"], prompt=step["prompt"],
                seed=spec.seed, params=result.params_used, parents=parents,
                asset_sha256=digest,
                asset_url=f"/api/assets/{digest}.{result.ext}",
                media_type=f"{'image' if result.ext in ('png','jpg','webp','gif') else 'video' if result.ext in ('mp4','webm') else 'audio'}/{result.ext}",
                size_bytes=len(result.data), cost_usd=result.cost_usd,
                sign=_gb_sign)
            if gb:
                storage.put_provenance(digest, "genblaze.json", gb)

            commit = Commit(hash=digest, project_id=job.project_id,
                            branch=job.branch, step_id=step_id,
                            job_id=job.id,
                            recipe_key=_recipe_key(step, job.input_hash),
                            modality=step["modality"], ext=result.ext,
                            parents=parents, recipe=recipe, evals=evals,
                            cost_usd=sum(e.get("cost_usd", 0) for e in evals),
                            latency_ms=result.latency_ms,
                            manifest_sig=manifest["signature"]["sig"])
            db.merge(commit)
            db.commit()
            storage.append_dag(job.project_id, json.dumps(
                {"hash": digest, "branch": job.branch, "step": step_id,
                 "modality": step["modality"], "ext": result.ext,
                 "parents": parents, "recipe": recipe,
                 "sig": manifest["signature"]["sig"]}))
            produced[step_id] = digest
            emit("step.commit", {"step": step_id, "hash": digest,
                                 "provider": result.provider,
                                 "score": evals[-1]["score"]})

        job.status = "done"
        job.total_cost_usd = total_cost
        db.commit()
        emit("job.done", {"cost_usd": round(total_cost, 4),
                          "commits": len(produced)})
    except Exception as e:  # keep the worker alive; surface the error
        job.status = "failed"
        db.commit()
        emit("job.failed", {"error": str(e)})
        raise
    finally:
        db.close()


def _index_reused(db, job: Job, step: dict, reuse: Commit,
                  parents: list[str], storage) -> None:
    """Record a dedup reference on the new branch (no new bytes stored)."""
    existing = db.query(Commit).filter_by(hash=reuse.hash, branch=job.branch).first()
    if existing:
        return
    # same content hash may appear on many branches — composite identity is
    # (hash, branch) in the DAG log; the index keeps first-seen row + log line
    storage.append_dag(job.project_id, json.dumps(
        {"hash": reuse.hash, "branch": job.branch, "step": step["id"],
         "modality": reuse.modality, "ext": reuse.ext, "parents": parents,
         "recipe": reuse.recipe, "sig": reuse.manifest_sig,
         "reused_from": job.base_branch}))
