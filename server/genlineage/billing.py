"""Billing via Flutterwave — recurring subscriptions.

Model (per Flutterwave's payment-plans API):
  * A "payment plan" exists per (tier, interval): standard/monthly,
    standard/yearly, premium/monthly, premium/yearly. Created once on demand
    and cached in our DB.
  * Checkout passes `payment_plan` so the customer is auto-subscribed on the
    first charge. Flutterwave then bills them each interval automatically —
    the customer never re-enters card details.
  * Cancelling calls Flutterwave's subscription cancel endpoint; the customer
    keeps access until the paid period ends, then falls back to Free.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import httpx

from .config import settings
from .models import Payment, PlanRef, SessionLocal, User

FLW_API = "https://api.flutterwave.com/v3"

# Prices per currency. Charging in the currency your account settles in avoids
# Flutterwave's FX conversion step (a common source of checkout failures).
PRICE_TABLE = {
    "USD": {
        ("standard", "monthly"): 10,
        ("standard", "yearly"): 105,
        ("premium", "monthly"): 25,
        ("premium", "yearly"): 264,
    },
    "NGN": {
        ("standard", "monthly"): 15000,
        ("standard", "yearly"): 158000,
        ("premium", "monthly"): 37500,
        ("premium", "yearly"): 396000,
    },
}


def _prices() -> dict:
    return PRICE_TABLE.get(settings.FLW_CURRENCY.upper(), PRICE_TABLE["USD"])


def _cycle(cycle: str) -> str:
    return "yearly" if cycle in ("yearly", "annual") else "monthly"


def price_for(plan: str, cycle: str) -> int | None:
    return _prices().get((plan, _cycle(cycle)))


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.FLW_SECRET_KEY}"}


def _require_keys() -> None:
    if not settings.flw_enabled:
        raise RuntimeError(
            "Flutterwave keys not configured — add FLW_SECRET_KEY to server/.env")


def _find_remote_plan(name: str, amount: int, currency: str,
                      interval: str) -> int | None:
    """Reuse an existing Flutterwave plan that matches exactly (name/amount/
    currency/interval). Prevents duplicate plans and currency mismatches."""
    try:
        r = httpx.get(f"{FLW_API}/payment-plans", headers=_headers(),
                      timeout=30)
        r.raise_for_status()
        for p in (r.json().get("data") or []):
            if (p.get("name") == name
                    and str(p.get("status", "active")).lower() == "active"
                    and float(p.get("amount", 0)) == float(amount)
                    and str(p.get("currency", "")).upper() == currency.upper()
                    and str(p.get("interval", "")).lower() == interval.lower()):
                return int(p["id"])
    except Exception:
        pass
    return None


def get_or_create_payment_plan(plan: str, cycle: str) -> int:
    """Flutterwave payment-plan id for this tier+interval+currency.

    Flutterwave requires the charge currency to equal the plan currency, so the
    cache key includes the currency — switching currency creates a new plan
    rather than reusing a mismatched one.
    """
    _require_keys()
    cycle = _cycle(cycle)
    amount = price_for(plan, cycle)
    if amount is None:
        raise ValueError("unknown plan/cycle")

    currency = settings.FLW_CURRENCY.upper()
    name = f"Genlineage {plan.title()} ({cycle}, {currency})"

    db = SessionLocal()
    try:
        key = f"{plan}:{cycle}:{currency}:{amount}"
        ref = db.get(PlanRef, key)
        if ref:
            return ref.flw_plan_id

        # a matching plan may already exist on the account (e.g. fresh DB)
        flw_id = _find_remote_plan(name, amount, currency, cycle)

        if flw_id is None:
            r = httpx.post(
                f"{FLW_API}/payment-plans",
                headers=_headers(),
                json={
                    "amount": amount,
                    "name": name,
                    "interval": cycle,
                    "currency": currency,
                },
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "success":
                raise RuntimeError(data.get("message", "Flutterwave error"))
            flw_id = int(data["data"]["id"])

        db.merge(PlanRef(key=key, plan=plan, cycle=cycle, amount=amount,
                         currency=currency, flw_plan_id=flw_id))
        db.commit()
        return flw_id
    finally:
        db.close()


def create_checkout(user: User, plan: str, cycle: str,
                    recurring: bool | None = None) -> dict:
    """Hosted checkout. With recurring=True (default) the customer is
    subscribed to a payment plan; set FLW_RECURRING=0 to charge one-off
    (useful when diagnosing plan/currency issues)."""
    _require_keys()
    cycle = _cycle(cycle)
    amount = price_for(plan, cycle)
    if amount is None:
        raise ValueError("unknown plan/cycle")

    currency = settings.FLW_CURRENCY.upper()
    if recurring is None:
        recurring = settings.FLW_RECURRING
    # NOTE (Flutterwave docs): attaching a payment_plan fixes the method to
    # card. When recurring is off we can offer bank transfer / USSD etc, which
    # route through a different processor — useful when their card sandbox 502s.
    flw_plan_id = get_or_create_payment_plan(plan, cycle) if recurring else None

    db = SessionLocal()
    try:
        tx_ref = f"gl-{user.id}-{secrets.token_hex(6)}"
        db.add(Payment(tx_ref=tx_ref, user_id=user.id, plan=plan, cycle=cycle,
                       amount=amount, currency=currency, status="pending"))
        db.commit()

        r = httpx.post(
            f"{FLW_API}/payments",
            headers=_headers(),
            json={
                "tx_ref": tx_ref,
                "amount": str(amount),
                "currency": currency,  # MUST equal the plan's currency
                "redirect_url": f"{settings.APP_URL}/studio",
                "customer": {"email": user.email, "name": user.name},
                "customizations": {
                    "title": "Genlineage",
                    "description": f"{plan.title()} — billed {cycle}",
                },
                **({"payment_plan": flw_plan_id} if flw_plan_id
                   else {"payment_options": settings.FLW_PAYMENT_OPTIONS}),
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            raise RuntimeError(data.get("message", "Flutterwave error"))
        return {"link": data["data"]["link"], "tx_ref": tx_ref,
                "recurring": bool(flw_plan_id), "amount": amount,
                "currency": currency, "payment_plan": flw_plan_id}
    finally:
        db.close()


def _period_end(cycle: str) -> datetime:
    now = datetime.now(timezone.utc)
    return now + (timedelta(days=365) if _cycle(cycle) == "yearly"
                  else timedelta(days=30))


def _activate(db, payment: Payment, flw_tx_id: str | None,
              subscription_id: str | None = None) -> None:
    if payment.status == "successful":
        return
    payment.status = "successful"
    payment.flw_tx_id = flw_tx_id
    payment.paid_at = datetime.now(timezone.utc)
    u = db.get(User, payment.user_id)
    if u:
        u.plan = payment.plan
        u.billing_cycle = payment.cycle
        u.subscription_status = "active"
        u.current_period_end = _period_end(payment.cycle)
        if subscription_id:
            u.flw_subscription_id = subscription_id
    db.commit()


def _find_subscription_id(email: str) -> str | None:
    try:
        r = httpx.get(f"{FLW_API}/subscriptions", headers=_headers(),
                      params={"email": email}, timeout=30)
        r.raise_for_status()
        items = r.json().get("data") or []
        active = [s for s in items if s.get("status") == "active"]
        chosen = active or items
        return str(chosen[0]["id"]) if chosen else None
    except Exception:
        return None


def verify_payment(user: User, tx_ref: str, transaction_id: str) -> dict:
    _require_keys()
    db = SessionLocal()
    try:
        payment = db.get(Payment, tx_ref)
        if not payment or payment.user_id != user.id:
            return {"ok": False, "detail": "Unknown payment reference."}
        if payment.status == "successful":
            return {"ok": True, "plan": payment.plan, "already": True}

        r = httpx.get(f"{FLW_API}/transactions/{transaction_id}/verify",
                      headers=_headers(), timeout=30)
        r.raise_for_status()
        d = r.json().get("data") or {}
        # Flutterwave may convert (e.g. USD charge settled in NGN): compare the
        # amount in the currency we requested, allowing a small FX rounding gap.
        paid = float(d.get("amount", 0) or 0)
        paid_ccy = d.get("currency")
        if paid_ccy != payment.currency:
            paid = float(d.get("charged_amount", 0) or 0) or paid
        amount_ok = paid >= payment.amount * 0.98  # 2% tolerance for FX rounding
        ok = (d.get("status") == "successful"
              and d.get("tx_ref") == tx_ref
              and amount_ok)
        if not ok:
            payment.status = "failed"
            db.commit()
            return {"ok": False,
                    "detail": f"Payment not verified (status={d.get('status')})."}

        _activate(db, payment, str(d.get("id")), _find_subscription_id(user.email))
        return {"ok": True, "plan": payment.plan}
    finally:
        db.close()


def cancel_subscription(user: User) -> dict:
    """Cancel recurring billing; access continues until the period ends."""
    db = SessionLocal()
    try:
        u = db.get(User, user.id)
        if u.plan == "free":
            return {"ok": False, "detail": "You're on the Free plan."}

        sub_id = u.flw_subscription_id or _find_subscription_id(u.email)
        if sub_id and settings.flw_enabled:
            try:
                httpx.put(f"{FLW_API}/subscriptions/{sub_id}/cancel",
                          headers=_headers(), timeout=30).raise_for_status()
            except httpx.HTTPError:
                pass  # already cancelled upstream — proceed locally

        u.subscription_status = "cancelled"
        db.commit()
        return {"ok": True, "plan": u.plan,
                "subscription_status": u.subscription_status,
                "current_period_end": (u.current_period_end.isoformat()
                                       if u.current_period_end else None)}
    finally:
        db.close()


def enforce_expiry(user: User) -> User:
    """Drop a cancelled subscription to Free once its paid period elapses."""
    if user.plan == "free" or user.subscription_status != "cancelled":
        return user
    end = user.current_period_end
    if not end:
        return user
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end > datetime.now(timezone.utc):
        return user
    db = SessionLocal()
    try:
        u = db.get(User, user.id)
        u.plan = "free"
        u.subscription_status = "none"
        u.flw_subscription_id = None
        u.current_period_end = None
        db.commit()
        return u
    finally:
        db.close()


def handle_webhook(body: dict) -> dict:
    event = body.get("event", "")
    data = body.get("data") or {}
    db = SessionLocal()
    try:
        if event.startswith("subscription") and "cancel" in event:
            email = ((data.get("customer") or {}).get("email")
                     or data.get("customer_email"))
            if email:
                u = db.query(User).filter_by(email=email).first()
                if u:
                    u.subscription_status = "cancelled"
                    db.commit()
            return {"ok": True}

        if data.get("status") != "successful":
            return {"ok": True, "ignored": True}

        tx_ref = data.get("tx_ref")
        payment = db.get(Payment, tx_ref) if tx_ref else None
        if payment:
            paid = float(data.get("amount", 0) or 0)
            if paid >= payment.amount * 0.98:
                _activate(db, payment, str(data.get("id")))
            return {"ok": True}

        # recurring renewal charge: extend the paid period
        email = ((data.get("customer") or {}).get("email")
                 or data.get("customer_email"))
        if email:
            u = db.query(User).filter_by(email=email).first()
            if u and u.plan != "free" and u.subscription_status == "active":
                u.current_period_end = _period_end(u.billing_cycle)
                db.commit()
        return {"ok": True}
    finally:
        db.close()
