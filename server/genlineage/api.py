"""Genlineage API — auth-light demo surface.

REST for projects / jobs / commits / DAG, WebSocket for live pipeline
status, asset streaming (local mode) or presigned URL passthrough (B2).
"""
from __future__ import annotations

import asyncio
import json
import time

import httpx

from fastapi import (Cookie, Depends, FastAPI, File, HTTPException, Request,
                     Response as Resp, UploadFile, WebSocket,
                     WebSocketDisconnect)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse,  Response
from pydantic import BaseModel

from . import jobs as jobq
from .auth import (SESSION_COOKIE, create_session, destroy_session,
                   get_current_user, require_verified, hash_password, verify_password)
from .mailer import send as send_mail, send_reset, send_support_ack, send_support_notify, send_verify
from .config import settings
from .billing import (cancel_subscription, create_checkout, enforce_expiry,
                      handle_webhook, price_for, verify_payment)
from .models import AuthSession, Commit, EmailToken, Job, Project, SessionLocal, User, init_db
from .signing import get_signing_key, public_key_hex, verify_manifest
from .storage import get_storage

app = FastAPI(title="Genlineage", version="2.0")
_origins = list({settings.APP_URL, "http://localhost:3000"})
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])

# server-enforced plan entitlements (bound to real accounts in the auth release)
PLAN_LIMITS = {
    "free": {
        "projects": 3, "commits_per_month": 200,
        "gate_tuning": False, "audit_export": False,
        "cost_analytics": False, "priority_queue": False,
        "video_secs": [4],
    },
    "standard": {
        "projects": None, "commits_per_month": 2000,
        "gate_tuning": False, "audit_export": False,
        "cost_analytics": True, "priority_queue": True,
        "video_secs": [4, 6],
    },
    "premium": {
        "projects": None, "commits_per_month": 10000,
        "gate_tuning": True, "audit_export": True,
        "cost_analytics": True, "priority_queue": True,
        "video_secs": [4, 6, 8],
    },
}


def _plan(name: str | None) -> dict:
    return PLAN_LIMITS.get((name or "free").lower(), PLAN_LIMITS["free"])


def _commits_this_month(db, user) -> int:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q = (db.query(Commit).join(Job, Commit.job_id == Job.id)
           .filter(Commit.created_at >= month_start)
           .filter((Job.owner_id == user.id) | (Job.owner_id.is_(None))))
    return q.count()


MEDIA = {"png": "image/png", "gif": "image/gif", "webp": "image/webp",
         "mp4": "video/mp4", "webm": "video/webm",
         "mp4": "video/mp4", "wav": "audio/wav", "mp3": "audio/mpeg",
         "json": "application/json"}


init_db()

VALID_PLANS = {"free", "standard", "premium"}


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str
    plan: str | None = None
    cycle: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: str | None = None
    email: str | None = None


class PlanIn(BaseModel):
    plan: str
    cycle: str | None = None


def _user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "plan": u.plan,
            "billing_cycle": u.billing_cycle, "via": u.via,
            "subscription_status": u.subscription_status or "none",
            "email_verified": bool(u.email_verified),
            "current_period_end": (u.current_period_end.isoformat()
                                   if u.current_period_end else None)}


def _set_cookie(response: Resp, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax",
                        max_age=30 * 24 * 3600, path="/", secure=settings.cookie_secure)


@app.post("/api/auth/register")
def register(body: RegisterIn, response: Resp):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(422, "Enter a valid email address.")
    if len(body.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters.")
    if not body.name.strip():
        raise HTTPException(422, "Name is required.")
    db = SessionLocal()
    try:
        if db.query(User).filter_by(email=email).first():
            raise HTTPException(409, "An account with this email already exists log in instead.")
        # accounts start on Free — paid plans activate through Flutterwave checkout
        cycle = body.cycle if body.cycle in ("monthly", "annual") else "monthly"
        u = User(name=body.name.strip(), email=email,
                 password_hash=hash_password(body.password),
                 plan="free", billing_cycle=cycle)
        db.add(u)
        db.commit()
        from .config import settings as _cfg
        email_sent = False
        if _cfg.mail_enabled:
            try:
                _tok = _issue_token(db, u.id, "verify", 24 * 60)
                email_sent = send_verify(u.email, f"{_cfg.API_URL}/api/auth/verify?token={_tok}")
                if not email_sent:
                    print(f"[register] verify email to {u.email} rejected by Resend see [mailer] log above")
            except Exception as e:
                print(f"[register] verify email raised: {e!r}")
        _set_cookie(response, create_session(db, u.id))
        out = _user_out(u)
        out["verification_email_sent"] = email_sent
        return out
    finally:
        db.close()


@app.post("/api/auth/login")
def login(body: LoginIn, response: Resp):
    db = SessionLocal()
    try:
        u = db.query(User).filter_by(email=body.email.strip().lower()).first()
        if not u or not verify_password(body.password, u.password_hash):
            raise HTTPException(401, "Invalid email or password.")
        _set_cookie(response, create_session(db, u.id))
        return _user_out(u)
    finally:
        db.close()


@app.post("/api/auth/logout")
def logout(response: Resp,
           gl_session: str | None = Cookie(default=None)):
    if gl_session:
        db = SessionLocal()
        try:
            destroy_session(db, gl_session)
        finally:
            db.close()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    u = enforce_expiry(user)
    out = _user_out(u)
    out["entitlements"] = _plan(u.plan)
    return out


@app.patch("/api/auth/profile")
def update_profile(body: ProfileIn, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        u = db.get(User, user.id)
        if body.name and body.name.strip():
            u.name = body.name.strip()
        if body.email and "@" in body.email:
            email = body.email.strip().lower()
            clash = db.query(User).filter(User.email == email, User.id != u.id).first()
            if clash:
                raise HTTPException(409, "That email is already in use.")
            u.email = email
        db.commit()
        return _user_out(u)
    finally:
        db.close()


@app.post("/api/auth/plan")
def change_plan(body: PlanIn, user: User = Depends(get_current_user)):
    if body.plan not in VALID_PLANS:
        raise HTTPException(422, "Unknown plan.")
    if body.plan != "free":
        raise HTTPException(402, "Paid plans are activated through checkout.")
    db = SessionLocal()
    try:
        u = db.get(User, user.id)
        u.plan = "free"
        db.commit()
        return _user_out(u)
    finally:
        db.close()


# ---- billing: Flutterwave -----------------------------------------------------
class CheckoutIn(BaseModel):
    plan: str
    cycle: str = "monthly"


class VerifyIn(BaseModel):
    tx_ref: str
    transaction_id: str


@app.post("/api/billing/checkout")
def billing_checkout(body: CheckoutIn, user: User = Depends(get_current_user)):
    if price_for(body.plan, body.cycle) is None:
        raise HTTPException(422, "Unknown plan or billing cycle.")
    try:
        return create_checkout(user, body.plan, body.cycle)
    except Exception as e:
        raise HTTPException(502, f"Couldn't start checkout: {e}")


@app.post("/api/billing/verify")
def billing_verify(body: VerifyIn, user: User = Depends(get_current_user)):
    result = verify_payment(user, body.tx_ref, body.transaction_id)
    if not result.get("ok"):
        raise HTTPException(402, result.get("detail", "Payment not verified."))
    return result


@app.post("/api/billing/cancel")
def billing_cancel(user: User = Depends(get_current_user)):
    result = cancel_subscription(user)
    if not result.get("ok"):
        raise HTTPException(400, result.get("detail", "Nothing to cancel."))
    return result


@app.get("/api/billing/debug")
def billing_debug(user: User = Depends(get_current_user)):
    """What we would send to Flutterwave, and what it has on file."""
    import httpx as _hx
    from .billing import FLW_API, _headers, price_for as _pf
    from .config import settings as cfg
    out = {
        "keys_configured": cfg.flw_enabled,
        "secret_key_prefix": (cfg.FLW_SECRET_KEY or "")[:12] or None,
        "currency": cfg.FLW_CURRENCY,
        "recurring_enabled": cfg.FLW_RECURRING,
        "app_url": cfg.APP_URL,
        "prices": {f"{p}/{c}": _pf(p, c)
                   for p in ("standard", "premium")
                   for c in ("monthly", "yearly")},
    }
    if cfg.flw_enabled:
        try:
            r = _hx.get(f"{FLW_API}/payment-plans", headers=_headers(), timeout=20)
            out["flutterwave_plans"] = [
                {"id": p.get("id"), "name": p.get("name"),
                 "amount": p.get("amount"), "currency": p.get("currency"),
                 "interval": p.get("interval"), "status": p.get("status")}
                for p in (r.json().get("data") or [])
            ][:20]
        except Exception as e:
            out["flutterwave_plans_error"] = str(e)
    return out


@app.post("/api/billing/webhook")
async def billing_webhook(request: Request):
    # Flutterwave signs webhooks with the verif-hash header you set in the dashboard
    from .config import settings as cfg
    if cfg.FLW_WEBHOOK_HASH:
        if request.headers.get("verif-hash") != cfg.FLW_WEBHOOK_HASH:
            raise HTTPException(401, "bad webhook signature")
    return handle_webhook(await request.json())


# ---- Google sign-in (OAuth 2.0 authorization code flow) ----------------------
import secrets as _secrets
from urllib.parse import urlencode

_oauth_states: dict[str, float] = {}   # csrf state -> created_at


@app.get("/api/auth/google/status")
def google_status():
    from .config import settings as cfg
    return {"enabled": cfg.google_enabled}


@app.get("/api/auth/google/start")
def google_start():
    """Step 1: redirect the browser to Google's consent screen."""
    from .config import settings as cfg
    if not cfg.google_enabled:
        raise HTTPException(503, "Google sign-in is not configured on this server.")
    state = _secrets.token_urlsafe(24)
    _oauth_states[state] = time.time()
    # drop states older than 10 minutes
    for k, t in list(_oauth_states.items()):
        if time.time() - t > 600:
            _oauth_states.pop(k, None)
    params = {
        "client_id": cfg.GOOGLE_CLIENT_ID,
        "redirect_uri": f"{cfg.API_URL}/api/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url, status_code=302)


@app.get("/api/auth/google/callback")
def google_callback(code: str | None = None, state: str | None = None,
                    error: str | None = None):
    """Step 2: exchange the code for the user's identity, then sign them in."""
    from .config import settings as cfg
    app_url = cfg.APP_URL
    if error or not code:
        return RedirectResponse(f"{app_url}/login?error=google_cancelled", 302)
    if not state or state not in _oauth_states:
        return RedirectResponse(f"{app_url}/login?error=bad_state", 302)
    _oauth_states.pop(state, None)

    try:
        tok = httpx.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": cfg.GOOGLE_CLIENT_ID,
            "client_secret": cfg.GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{cfg.API_URL}/api/auth/google/callback",
            "grant_type": "authorization_code",
        }, timeout=30)
        if tok.status_code != 200:
            # Google explains exactly what's wrong here — surface it
            print(f"[google-oauth] token exchange failed {tok.status_code}: {tok.text}")
            print(f"[google-oauth] redirect_uri sent: {cfg.API_URL}/api/auth/google/callback")
            return RedirectResponse(f"{app_url}/login?error=google_token", 302)
        access_token = tok.json().get("access_token")
        if not access_token:
            print(f"[google-oauth] no access_token in response: {tok.text}")
            return RedirectResponse(f"{app_url}/login?error=google_token", 302)

        info = httpx.get("https://www.googleapis.com/oauth2/v3/userinfo",
                         headers={"Authorization": f"Bearer {access_token}"},
                         timeout=30)
        if info.status_code != 200:
            print(f"[google-oauth] userinfo failed {info.status_code}: {info.text}")
            return RedirectResponse(f"{app_url}/login?error=google_userinfo", 302)
        profile = info.json()
    except Exception as e:
        import traceback
        print(f"[google-oauth] exception: {e!r}")
        traceback.print_exc()
        return RedirectResponse(f"{app_url}/login?error=google_failed", 302)

    email = (profile.get("email") or "").strip().lower()
    if not email or not profile.get("email_verified", True):
        return RedirectResponse(f"{app_url}/login?error=google_email", 302)

    db = SessionLocal()
    try:
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(name=profile.get("name") or email.split("@")[0],
                     email=email,
                     # OAuth accounts have no usable password: store an
                     # unguessable hash so password login can never succeed
                     password_hash=hash_password(_secrets.token_urlsafe(32)),
                     plan="free", via="google", email_verified=True)
            db.add(u)
            db.commit()
        token = create_session(db, u.id)
    finally:
        db.close()

    resp = RedirectResponse(f"{app_url}/studio", status_code=302)
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax",
                    max_age=30 * 24 * 3600, path="/", secure=settings.cookie_secure)
    return resp


from datetime import datetime, timedelta, timezone as _tz


def _issue_token(db, user_id: str, kind: str, minutes: int) -> str:
    tok = _secrets.token_urlsafe(32)
    db.add(EmailToken(token=tok, user_id=user_id, kind=kind,
                      expires_at=datetime.now(_tz.utc) + timedelta(minutes=minutes)))
    db.commit()
    return tok


def _consume_token(db, token: str, kind: str):
    t = db.get(EmailToken, token or "")
    if not t or t.kind != kind or t.used:
        return None
    exp = t.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=_tz.utc)
    if exp < datetime.now(_tz.utc):
        return None
    t.used = True
    db.commit()
    return t.user_id


@app.post("/api/auth/verify/send")
def verify_send(user: User = Depends(get_current_user)):
    from .config import settings as cfg
    if user.email_verified:
        return {"ok": True, "already": True}
    if not cfg.mail_enabled:
        raise HTTPException(503, "We can't send the verification email right now. "
                                 "Please try again shortly.")
    db = SessionLocal()
    try:
        tok = _issue_token(db, user.id, "verify", 24 * 60)
    finally:
        db.close()
    sent = send_verify(user.email, f"{cfg.API_URL}/api/auth/verify?token={tok}")
    if not sent:
        raise HTTPException(502, "We couldn't send that email — check the server log, or try again shortly.")
    return {"ok": True}

@app.get("/api/auth/verify")
def verify_email(token: str = ""):
    from .config import settings as cfg
    db = SessionLocal()
    try:
        uid = _consume_token(db, token, "verify")
        if not uid:
            return RedirectResponse(f"{cfg.APP_URL}/studio?verify=expired", 302)
        u = db.get(User, uid)
        u.email_verified = True
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"{cfg.APP_URL}/studio?verify=ok", 302)


class ResetIn(BaseModel):
    token: str
    password: str


@app.post("/api/auth/reset")
def reset_password(body: ResetIn):
    if len(body.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters.")
    db = SessionLocal()
    try:
        uid = _consume_token(db, body.token, "reset")
        if not uid:
            raise HTTPException(400, "This reset link is invalid or expired.")
        u = db.get(User, uid)
        u.password_hash = hash_password(body.password)
        db.query(AuthSession).filter_by(user_id=uid).delete()  # revoke everywhere
        db.commit()
    finally:
        db.close()
    return {"ok": True}


class SupportIn(BaseModel):
    subject: str | None = None
    message: str
    name: str | None = None
    email: str | None = None
    topic: str | None = None
    turnstile_token: str | None = None


@app.get("/api/turnstile")
def turnstile_key():
    from .config import settings as cfg
    return {"site_key": cfg.TURNSTILE_SITE_KEY or None}


@app.post("/api/auth/delete-account")
def delete_account(response: Resp, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        pids = [p.id for p in db.query(Project).filter_by(owner_id=user.id)]
        for pid in pids:
            db.query(Commit).filter_by(project_id=pid).delete()
            db.query(Job).filter_by(project_id=pid).delete()
        db.query(Project).filter_by(owner_id=user.id).delete()
        db.query(EmailToken).filter_by(user_id=user.id).delete()
        db.query(AuthSession).filter_by(user_id=user.id).delete()
        db.query(User).filter_by(id=user.id).delete()
        db.commit()
    finally:
        db.close()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@app.post("/api/support")
def support(body: SupportIn, gl_session: str | None = Cookie(default=None)):
    from .config import settings as cfg
    if not cfg.mail_enabled:
        raise HTTPException(503, "Our contact form is temporarily unavailable. "
                                 f"Please email us at {cfg.SUPPORT_EMAIL}.")
    # works logged-in or not: fall back to the details typed on the page
    from .auth import user_from_token
    user = user_from_token(gl_session) if gl_session else None
    sender_email = (body.email or (user.email if user else "")).strip().lower()
    sender_name = (body.name or (user.name if user else "")).strip() or "Anonymous"
    if "@" not in sender_email:
        raise HTTPException(422, "A valid email address is required.")
    subject = (body.subject or body.topic or "Support request").strip()[:120]
    if cfg.TURNSTILE_SECRET:
        try:
            tv = httpx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                            data={"secret": cfg.TURNSTILE_SECRET,
                                  "response": body.turnstile_token or ""},
                            timeout=15).json()
        except Exception:
            tv = {"success": False}
        if not tv.get("success"):
            raise HTTPException(400, "The bot check didn't pass. Please refresh "
                                     "the page and try again.")
    ticket = f"GL-{_secrets.token_hex(3).upper()}"
    plan_line = f" · plan {user.plan}" if user else " · not signed in"
    ok = send_support_notify(cfg.SUPPORT_EMAIL, ticket, subject, sender_name,
                             sender_email, plan_line, body.topic or "—",
                             body.message.strip()[:4000], reply_to=sender_email)
    if not ok:
        # the real reason is printed to the server log by mailer.send()
        raise HTTPException(502, "We couldn't send your message just now. Please "
                                 "try again in a few minutes — or email us "
                                 f"directly at {cfg.SUPPORT_EMAIL}.")
    send_support_ack(sender_email, ticket, subject)
    return {"ok": True, "ticket": ticket}


class ForgotIn(BaseModel):
    email: str


@app.post("/api/auth/forgot")
def forgot(body: ForgotIn):
    from .config import settings as cfg
    db = SessionLocal()
    try:
        u = db.query(User).filter_by(email=body.email.strip().lower()).first()
        if u and cfg.mail_enabled and (u.via or "email") == "email":
            tok = _issue_token(db, u.id, "reset", 30)
            send_reset(u.email, f"{cfg.APP_URL}/reset?token={tok}")
    finally:
        db.close()
    # identical response whether or not the account exists (no enumeration)
    return {"ok": True, "detail": "If that email has an account, a reset link is on its way."}


# ---- projects ---------------------------------------------------------------
class ProjectIn(BaseModel):
    name: str
    plan: str | None = None  # ignored — plan comes from the account


def _owned(query, model, user):
    """User's rows plus legacy pre-auth rows (owner_id null)."""
    return query.filter((model.owner_id == user.id) | (model.owner_id.is_(None)))


@app.post("/api/projects")
def create_project(body: ProjectIn, user: User = Depends(require_verified)):
    db = SessionLocal()
    try:
        limit = _plan(user.plan)["projects"]
        if limit is not None and _owned(db.query(Project), Project, user).count() >= limit:
            raise HTTPException(402, f"Free plan includes {limit} projects — upgrade to add more.")
        p = Project(name=body.name, owner_id=user.id)
        db.add(p)
        db.commit()
        return {"id": p.id, "name": p.name}
    finally:
        db.close()


@app.get("/api/projects")
def list_projects(user: User = Depends(require_verified)):
    db = SessionLocal()
    try:
        out = []
        for p in _owned(db.query(Project), Project, user).order_by(Project.created_at.desc()).all():
            commits = db.query(Commit).filter_by(project_id=p.id).count()
            out.append({"id": p.id, "name": p.name, "commits": commits,
                        "created_at": p.created_at.isoformat()})
        return out
    finally:
        db.close()


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, user: User = Depends(get_current_user)):
    """Delete a project: its jobs, commit index rows, and DAG log.

    Underlying assets stay in the content store — they're content-addressed
    and may be referenced by other projects; orphans are lifecycle-cleaned.
    """
    db = SessionLocal()
    storage = get_storage()
    try:
        p = db.get(Project, project_id)
        if not p:
            raise HTTPException(404, "project not found")
        if p.owner_id and p.owner_id != user.id:
            raise HTTPException(403, "not your project")
        db.query(Commit).filter_by(project_id=project_id).delete()
        db.query(Job).filter_by(project_id=project_id).delete()
        db.delete(p)
        db.commit()
        storage.delete_dag(project_id)
        return {"deleted": project_id}
    finally:
        db.close()


# ---- uploads: user product images enter the content-addressed store ---------
UPLOAD_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


@app.post("/api/uploads")
async def upload_image(file: UploadFile = File(...)):
    ext = UPLOAD_TYPES.get(file.content_type)
    if not ext:
        raise HTTPException(415, "png, jpeg or webp only")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "max 10MB")
    storage = get_storage()
    digest = storage.put_asset(data, ext)
    return {"hash": digest, "ext": ext, "url": storage.asset_url(digest, ext)}


# ---- jobs -------------------------------------------------------------------
class JobIn(BaseModel):
    brief: str
    branch: str = "main"
    base_branch: str | None = None  # set → remix with dedup
    gate_min: float | None = None   # per-run quality-gate override
    input_hash: str | None = None   # uploaded product image (from /api/uploads)
    input_ext: str | None = None
    voice_script: str | None = None
    voice: str | None = None          # Kore/Leda (female) · Charon/Puck (male)
    music_style: str | None = None    # preset name or "none"
    n_shots: int | None = None        # 2-4
    video_secs: int | None = None     # 4/6/8 per shot
    plan: str | None = "free"


@app.post("/api/projects/{project_id}/jobs")
def create_job(project_id: str, body: JobIn, user: User = Depends(require_verified)):
    db = SessionLocal()
    try:
        proj = db.get(Project, project_id)
        if not proj:
            raise HTTPException(404, "project not found")
        if proj.owner_id and proj.owner_id != user.id:
            raise HTTPException(403, "not your project")
        ent = _plan(user.plan)
        used = _commits_this_month(db, user)
        if used >= ent["commits_per_month"]:
            raise HTTPException(
                402, f"Monthly commit allowance reached ({used}/{ent['commits_per_month']}) — upgrade your plan.")
        gate = body.gate_min if ent["gate_tuning"] else None  # Premium feature
        job = Job(owner_id=user.id,
                  project_id=project_id, brief=body.brief, branch=body.branch,
                  base_branch=body.base_branch, gate_min=gate,
                  input_hash=body.input_hash, input_ext=body.input_ext,
                  voice_script=(body.voice_script or "").strip() or None,
                  voice=body.voice or None,
                  music_style=body.music_style or None,
                  n_shots=(max(2, min(body.n_shots, 4)) if body.n_shots else None),
                  video_secs=(body.video_secs if body.video_secs in
                              _plan(user.plan).get("video_secs", [4]) else None),
                  events=[])
        if body.gate_min is not None and not ent["gate_tuning"]:
            job.events = [{"event": "plan.notice",
                           "at": job.created_at.isoformat() if job.created_at else "",
                           "note": "Quality-gate tuning is a Premium feature — default threshold used."}]
        db.add(job)
        db.commit()
        jobq.enqueue(job.id, user.plan or "free")
        return {"id": job.id, "status": "queued"}
    finally:
        db.close()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, user: User = Depends(require_verified)):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        return {"id": job.id, "project_id": job.project_id, "brief": job.brief,
                "branch": job.branch, "base_branch": job.base_branch,
                "status": job.status, "events": job.events or [],
                "total_cost_usd": (job.total_cost_usd
                                   if _plan(user.plan)["cost_analytics"] else None)}
    finally:
        db.close()


# Short-lived tickets for the pipeline WebSocket.
#
# The session cookie is SameSite=Lax, so it is NOT sent on a cross-site socket
# handshake (browser → Railway). The client mints a ticket over the ordinary
# same-origin API call, where the cookie does work, and presents it here.
#
# Tickets are STATELESS: an ed25519-signed payload, verified with the same key
# that signs provenance manifests. No server-side store, so any instance can
# validate a ticket minted by any other — this survives horizontal scaling.
# The trade-off is that a ticket is replayable until it expires, hence the very
# short TTL.
import base64 as _b64

WS_TICKET_TTL = 30


def _make_ws_ticket(user_id: str, ttl: int = WS_TICKET_TTL) -> str:
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + ttl},
                         sort_keys=True, separators=(",", ":")).encode()
    sig = get_signing_key().sign(payload).signature
    body = _b64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{body}.{sig.hex()}"


def _read_ws_ticket(ticket: str) -> str | None:
    """Return the user id iff the signature is valid and the ticket is live."""
    try:
        body, sig_hex = ticket.split(".", 1)
        payload = _b64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        get_signing_key().verify_key.verify(payload, bytes.fromhex(sig_hex))
        data = json.loads(payload)
        if int(data["exp"]) < time.time():
            return None
        return data["uid"]
    except Exception:
        return None


@app.post("/api/ws-ticket")
def ws_ticket(user: User = Depends(get_current_user)):
    return {"ticket": _make_ws_ticket(user.id), "expires_in": WS_TICKET_TTL}


@app.websocket("/ws/jobs/{job_id}")
async def job_stream(ws: WebSocket, job_id: str, ticket: str | None = None,
                     gl_session: str | None = Cookie(default=None)):
    # identity: ticket first (works cross-site), session cookie as the
    # same-origin fallback for local development
    uid = _read_ws_ticket(ticket) if ticket else None
    if uid is None and gl_session:
        from .auth import user_from_token
        u = user_from_token(gl_session)
        uid = u.id if u else None
    if uid is None:
        await ws.close(code=4401)                   # not authenticated
        return

    db = SessionLocal()
    job = db.get(Job, job_id)
    db.close()
    if not job:
        await ws.close(code=4404)
        return
    if job.owner_id and job.owner_id != uid:        # legacy rows have no owner
        await ws.close(code=4403)                   # not your job
        return
    await ws.accept()
    q = jobq.subscribe(job_id)
    try:
        for entry in job.events or []:  # replay history first
            await ws.send_json(entry)
        if job.status in ("done", "failed"):
            await ws.close()
            return
        loop = asyncio.get_event_loop()
        while True:
            entry = await loop.run_in_executor(None, q.get)
            if entry is None:
                break
            await ws.send_json(entry)
        await ws.close()
    except WebSocketDisconnect:
        pass
    finally:
        jobq.unsubscribe(job_id, q)


# ---- works: the user's previous runs, gallery-style -------------------------
@app.get("/api/works")
def list_works(limit: int = 50, user: User = Depends(require_verified)):
    """Recent completed runs across all projects, newest first, each with a
    representative thumbnail (final cut, else last visual commit)."""
    db = SessionLocal()
    storage = get_storage()
    try:
        analytics = _plan(user.plan)["cost_analytics"]
        jobs = (_owned(db.query(Job), Job, user)
                  .filter(Job.status.in_(["done", "failed"]))
                  .order_by(Job.created_at.desc()).limit(limit).all())
        projects = {p.id: p.name for p in db.query(Project).all()}
        out = []
        for j in jobs:
            commits = (db.query(Commit).filter_by(job_id=j.id)
                         .order_by(Commit.created_at.asc()).all())
            if not commits:  # runs from before job linkage: fall back to branch
                commits = (db.query(Commit)
                             .filter_by(project_id=j.project_id, branch=j.branch)
                             .order_by(Commit.created_at.asc()).all())
            visual = [c for c in commits if c.modality in ("image", "video")]
            thumb = next((c for c in visual if c.step_id == "final-cut"),
                         visual[-1] if visual else None)
            out.append({
                "job_id": j.id,
                "project_id": j.project_id,
                "project": projects.get(j.project_id, "(deleted project)"),
                "branch": j.branch,
                "brief": j.brief,
                "status": j.status,
                "commits": len(commits),
                "cost_usd": (j.total_cost_usd if analytics else None),
                "created_at": j.created_at.isoformat(),
                "thumb_url": storage.asset_url(thumb.hash, thumb.ext) if thumb else None,
                "thumb_modality": thumb.modality if thumb else None,
            })
        return out
    finally:
        db.close()


@app.delete("/api/works/{job_id}")
def delete_work(job_id: str, user: User = Depends(get_current_user)):
    """Delete a run: its job record, its commit index rows, and its lines in
    the project DAG log. Content-addressed bytes stay (may be shared)."""
    db = SessionLocal()
    storage = get_storage()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "work not found")
        if job.owner_id and job.owner_id != user.id:
            raise HTTPException(403, "not your work")
        commits = db.query(Commit).filter_by(job_id=job_id).all()
        gone = {(c.hash, c.branch) for c in commits}
        for c in commits:
            db.delete(c)
        db.delete(job)
        db.commit()
        # dedup-referenced steps have DAG lines but no commit rows; drop them
        # too when this was the branch's last run
        branch_empty = (db.query(Job)
                          .filter_by(project_id=job.project_id, branch=job.branch)
                          .count() == 0)
        if gone or branch_empty:
            kept = []
            for line in storage.read_dag(job.project_id):
                entry = json.loads(line)
                drop = (entry.get("hash"), entry.get("branch")) in gone or (
                    branch_empty and entry.get("branch") == job.branch)
                if not drop:
                    kept.append(line)
            storage.delete_dag(job.project_id)
            for line in kept:
                storage.append_dag(job.project_id, line)
        return {"deleted": job_id, "commits_removed": len(gone)}
    finally:
        db.close()


# ---- DAG / commits ------------------------------------------------------------
@app.get("/api/projects/{project_id}/dag")
def get_dag(project_id: str, user: User = Depends(require_verified)):
    """Graph straight from the append-only log — the tamper-evident view."""
    db = SessionLocal()
    try:
        p = db.get(Project, project_id)
        if not p:
            raise HTTPException(404, "project not found")
        if p.owner_id and p.owner_id != user.id:
            raise HTTPException(403, "not your project")
    finally:
        db.close()
    storage = get_storage()
    nodes, edges, seen = [], [], set()
    for line in storage.read_dag(project_id):
        entry = json.loads(line)
        node_id = f"{entry['hash'][:12]}@{entry['branch']}"
        if node_id in seen:
            continue
        seen.add(node_id)
        nodes.append({"id": node_id, "hash": entry["hash"],
                      "branch": entry["branch"], "step": entry.get("step"),
                      "modality": entry.get("modality"), "ext": entry.get("ext"),
                      "reused_from": entry.get("reused_from"),
                      "provider": entry.get("recipe", {}).get("provider"),
                      "url": storage.asset_url(entry["hash"], entry.get("ext", "png"))})
        for parent in entry.get("parents", []):
            edges.append({"from": parent, "to": entry["hash"],
                          "branch": entry["branch"]})
    return {"nodes": nodes, "edges": edges}


def _genblaze_info(digest: str):
    """Genblaze SDK manifest verification for a commit, if one was stored."""
    try:
        raw = get_storage().get_provenance(digest, "genblaze.json")
        if not raw:
            return None
        from .genblaze_bridge import verify_manifest as _gv
        v = _gv(raw)
        return {"present": True, "verified": v.get("ok", False),
                "canonical_hash": v.get("canonical_hash"),
                "schema_version": v.get("schema_version")}
    except Exception:
        return None


@app.get("/api/commits/{digest}")
def get_commit(digest: str, user: User = Depends(require_verified)):
    db = SessionLocal()
    storage = get_storage()
    try:
        c = db.query(Commit).filter_by(hash=digest).first()
        if not c:
            raise HTTPException(404, "commit not found")
        manifest_raw = storage.get_provenance(digest, "manifest.json")
        manifest = json.loads(manifest_raw) if manifest_raw else None
        return {"hash": c.hash, "branch": c.branch, "step_id": c.step_id,
                "modality": c.modality, "ext": c.ext, "parents": c.parents,
                "recipe": c.recipe, "evals": c.evals,
                "genblaze": _genblaze_info(digest),
                "cost_usd": (c.cost_usd
                             if _plan(user.plan)["cost_analytics"] else None),
                "latency_ms": c.latency_ms, "manifest": manifest,
                "manifest_valid": verify_manifest(manifest) if manifest else False,
                "url": storage.asset_url(c.hash, c.ext),
                "created_at": c.created_at.isoformat()}
    finally:
        db.close()


@app.get("/api/verify/{digest}")
def verify(digest: str):
    storage = get_storage()
    raw = storage.get_provenance(digest, "manifest.json")
    if not raw:
        raise HTTPException(404, "no manifest for this hash")
    manifest = json.loads(raw)
    return {"hash": digest, "valid": verify_manifest(manifest),
            "public_key": public_key_hex(),
            "claim": manifest.get("claim")}


# ---- assets (local mode streaming; B2 mode returns presigned URLs in dag/commit)
@app.get("/api/assets/{filename}")
def get_asset(filename: str):
    digest, _, ext = filename.partition(".")
    storage = get_storage()
    if not storage.has_asset(digest, ext):
        raise HTTPException(404, "asset not found")
    return Response(content=storage.get_asset(digest, ext),
                    media_type=MEDIA.get(ext, "application/octet-stream"),
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/api/projects/{project_id}/audit")
def audit_export(project_id: str, user: User = Depends(get_current_user)):
    """Premium: full audit bundle — DAG log, every manifest, public key."""
    if not _plan(user.plan)["audit_export"]:
        raise HTTPException(402, "Audit exports are a Premium feature.")
    db = SessionLocal()
    storage = get_storage()
    try:
        p = db.get(Project, project_id)
        if not p:
            raise HTTPException(404, "project not found")
        lines = [json.loads(l) for l in storage.read_dag(project_id)]
        manifests = {}
        for entry in lines:
            h = entry["hash"]
            if h not in manifests:
                raw = storage.get_provenance(h, "manifest.json")
                if raw:
                    manifests[h] = json.loads(raw)
        from datetime import datetime, timezone
        bundle = {"project": {"id": p.id, "name": p.name},
                  "exported_at": datetime.now(timezone.utc).isoformat(),
                  "public_key": public_key_hex(),
                  "dag": lines, "manifests": manifests}
        return Response(
            content=json.dumps(bundle, indent=2),
            media_type="application/json",
            headers={"Content-Disposition":
                     f'attachment; filename="genlineage-audit-{p.id}.json"'})
    finally:
        db.close()


@app.get("/api/health")
def health():
    from .config import settings
    return {"ok": True, "storage": "b2" if settings.b2_enabled else "local",
            "public_key": public_key_hex()}
