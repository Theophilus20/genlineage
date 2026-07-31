# GEN_LINEAGE Git for generative media

Every generation has a history. Genlineage records each output as an immutable,
content addressed **commit** containing both the asset and the complete recipe
that produced it, evaluates it through an **agentic evaluator**, connects it in
a **remix DAG**, and ships it with a **signed provenance manifest**, so every
asset can be traced back to its origin.

Storage is Backblaze B2. Provenance is emitted in both a native signed format
and the official [Genblaze](https://github.com/backblaze-labs/genblaze) manifest
schema.

---

## How it works

A brief expands into a step graph, and every step streams to the browser over
WebSocket:

| Phase | |
|---|---|
| **Plan** | brief → storyboard frames → animated shots → voiceover → music bed → grain pass → final cut |
| **Generate** | each step dispatched to a provider chain with automatic failover |
| **Evaluate** | a vision model scores the output against the step's spec |
| **Retry** | below threshold, the critique is folded into revised params; a failing path hands off to the next provider |
| **Commit** | asset content-addressed by sha256, recipe + lineage signed with ed25519, appended to the project's DAG log |

Provider chains:

| Modality | Chain |
|---|---|
| Image | `fal` FLUX → `replicate:sdxl` → `gemini:flash-image` |
| Video | `openrouter:video` (`google/veo-3.1-lite`) → `fal:kling-v2` → `fal:hailuo` |
| Voice | `elevenlabs` → `gemini:tts` → `fal` |
| Music | `fal:musicgen` |
| Final cut | `genlineage:compositor` |

Video steps use image-to-video: a shot animates the storyboard frame it descends
from in the DAG, so the graph edge is causal.

The final cut is assembly, not generation. An ffmpeg compositor concatenates the
shots with crossfades, fades from and to black, lays the voiceover over a ducked
and looped music bed, and blends the grain pass on top. Its recipe records which
commits it was cut from.

## Quickstart

```bash
# backend
cd server
pip install -r requirements.txt
uvicorn genlineage.api:app --port 8000

# frontend
cd web
npm install
npm run dev          # http://localhost:3000
```

Optional: `python tools/seed_demo.py` seeds a main branch plus a remix to
demonstrate dedup.

## Configuration

Add keys to `server/.env` and each subsystem switches from mock to live,
independently. Nothing is required; missing keys degrade rather than break.
**`server/.env.example` is the authoritative list.**

| Key | Enables |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter video (Veo, Wan, Grok, Sora) |
| `OPENROUTER_VIDEO_MODEL` | model slug, default `google/veo-3.1-lite` |
| `GEMINI_API_KEY` | planning, image generation, TTS, quality gate |
| `FAL_KEY` | fal.ai FLUX / Kling / Hailuo / MusicGen |
| `REPLICATE_API_TOKEN` | Replicate failover |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS |
| `B2_KEY_ID`, `B2_APP_KEY`, `B2_BUCKET`, `B2_ENDPOINT` | Backblaze B2 (else local `data/`) |
| `DATABASE_URL` | Postgres (else SQLite) |
| `GENLINEAGE_SIGNING_KEY` | ed25519 seed, hex — required in production |
| `GENLINEAGE_APP_URL`, `GENLINEAGE_API_URL` | public URLs; drive CORS and cookie `Secure` |
| `RESEND_API_KEY`, `MAIL_FROM`, `SUPPORT_EMAIL` | transactional email |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in |
| `FLW_SECRET_KEY`, `FLW_WEBHOOK_HASH` | Flutterwave subscriptions |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET` | bot check on the support form |

`GENLINEAGE_MOCK` controls provider selection: `auto` (default — live wherever a
key exists), `1` (force mock), `0` (never mock).

Plan entitlements project count, monthly commits, shot length, cost analytics,
gate tuning, audit export are enforced server-side in `api.py:PLAN_LIMITS`, so
a modified client cannot bypass them.

## Architecture

```
server/genlineage/
  api.py                 REST + WebSocket surface, plan enforcement
  auth.py                sessions, bcrypt password hashing
  billing.py             Flutterwave checkout, verification, webhooks
  config.py              env loading; every subsystem's on/off switch
  jobs.py                priority queue
  mailer.py              Resend + HTML email templates
  models.py              SQLAlchemy index — rebuildable from dag.jsonl
  signing.py             ed25519 manifests
  genblaze_bridge.py     Genblaze manifest build + verify
  pipeline/runner.py     the five phases, dedup, failover, commit
  providers/
    openrouter.py        async video jobs (submit → poll → download)
    gemini.py            paced image + TTS with 429 backoff
    compositor.py        ffmpeg final cut
    mock.py              deterministic seeded assets, no network
  llm/                   planner + evaluator
  storage/               b2.py, local.py — identical layout behind one interface
web/
  app/studio/            React Flow remix DAG, commit inspector, live feed
  app/                   landing, auth, support, legal pages
  components/
tools/
  seed_demo.py, extract_characters.py
```

Storage layout, identical for B2 and local dev:

```
assets/sha256/ab/cd/<hash>.<ext>      immutable, content-addressed
derivatives/<hash>/thumb.webp
provenance/<hash>/manifest.json       native signed recipe + lineage
provenance/<hash>/genblaze.json       Genblaze manifest
provenance/<hash>/eval_log.json       every attempt, score, cost
graph/projects/<id>/dag.jsonl         append-only commit log
failures/<job>/<attempt>.<ext>        rejects (lifecycle: delete after 7d)
```

The database is only an index. The append-only log plus the manifests are the
record; the index can be rebuilt from them.

## Provenance

Every newly generated commit carries two interoperable records:

- **Native manifest** — provider, model, prompt, params, seed, parents and
  evaluation scores, signed with ed25519. Verify at `GET /api/verify/{hash}`,
  which returns the public key.
- **Genblaze manifest** — built with `genblaze-core`: a canonical,
  SHA-256-bound `Run`/`Step`/`Asset` record (schema 1.5) signed with the same
  key. Verification re-derives the canonical hash, so any alteration is
  detected.

Steps that are dedup-referenced on a remix carry the manifest from their
original commit rather than a new one.

## API

| | |
|---|---|
| Auth | `POST /api/auth/register` · `/login` · `/logout` · `/delete-account` · `GET /api/auth/me` · `PATCH /api/auth/profile` |
| Email | `POST /api/auth/verify/send` · `GET /api/auth/verify` · `POST /api/auth/forgot` · `/api/auth/reset` |
| Google | `GET /api/auth/google/status` · `/start` · `/callback` |
| Projects | `POST` / `GET /api/projects` · `DELETE /api/projects/{id}` · `GET /api/projects/{id}/dag` · `/audit` |
| Jobs | `POST /api/projects/{id}/jobs` · `GET /api/jobs/{id}` · `WS /ws/jobs/{id}` |
| Works | `GET /api/works` · `DELETE /api/works/{job_id}` |
| Commits | `GET /api/commits/{hash}` · `/api/verify/{hash}` · `/api/assets/{hash}.{ext}` |
| Uploads | `POST /api/uploads` — png/jpeg/webp, max 10 MB |
| Billing | `POST /api/billing/checkout` · `/verify` · `/cancel` · `/webhook` |
| Misc | `POST /api/support` · `GET /api/turnstile` · `GET /api/health` |

## Deployment

Backend on Railway (root directory `server`, plus a PostgreSQL service);
frontend on Vercel (root directory `web`, env `GENLINEAGE_API` → the Railway
URL); assets on B2.

Three things must move off local disk, because hosted filesystems reset on every
deploy:

| Local | Production |
|---|---|
| `genlineage.db` | Postgres via `DATABASE_URL` |
| `.signing_key` | `GENLINEAGE_SIGNING_KEY` |
| `server/data/` | Backblaze B2 |

The signing key matters most: if it regenerates, every previously signed
manifest fails verification. `signing.py` refuses to auto-generate one when
`GENLINEAGE_APP_URL` is a real domain, failing at boot rather than silently
invalidating provenance. Read the existing key with:

```bash
cd server && python -c "print(open('.signing_key','rb').read().hex())"
```

`GET /api/health` returns the active storage backend and the public key; the
public key must stay identical across deploys.

Set one B2 lifecycle rule in the console: `failures/` → delete after 7 days.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
