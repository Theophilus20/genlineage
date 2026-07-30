"""Transactional email via Resend."""
from __future__ import annotations

import httpx

from .config import settings


def send(to: str, subject: str, html: str, reply_to: str | None = None) -> bool:
    if not settings.mail_enabled:
        return False
    try:
        r = httpx.post("https://api.resend.com/emails",
                       headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                       json={"from": settings.MAIL_FROM, "to": [to],
                             "subject": subject, "html": html,
                             **({"reply_to": [reply_to]} if reply_to else {})},
                       timeout=30)
        if r.status_code not in (200, 201):
            print(f"[mailer] resend rejected ({r.status_code}): {r.text[:300]}")
            return False
        return True
    except httpx.HTTPError as e:
        print(f"[mailer] resend unreachable: {e}")
        return False


def _shell(title: str, body: str, cta_url: str = "", cta_label: str = "") -> str:
    """Branded HTML wrapper — matches the product: paper, ink, orange accent."""
    from .config import settings as _s
    is_local = "localhost" in _s.APP_URL or "127.0.0.1" in _s.APP_URL
    logo = "" if is_local else f"{_s.APP_URL}/logo.png"
    site = "" if is_local else _s.APP_URL.replace("https://", "").replace("http://", "")
    btn = ("" if not cta_url else f'''
      <tr><td style="padding:26px 34px 6px">
        <a href="{cta_url}" style="display:inline-block;padding:13px 26px;
           background:#e84b0f;color:#ffffff;text-decoration:none;
           font:600 13px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
           letter-spacing:.06em;text-transform:uppercase">{cta_label}</a>
      </td></tr>''')
    return f'''<!doctype html><html><body style="margin:0;background:#f4f4f1;
      font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#111110">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="background:#f4f4f1;padding:34px 16px">
        <tr><td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="max-width:520px;background:#fdfdfb;border:1px solid #d8d6cf">
            <tr><td style="padding:28px 34px 0">
              {f'<img src="{logo}" width="34" height="34" alt="" style="display:block;border:0;margin-bottom:16px">' if logo else ''}
              <div style="font-size:12px;letter-spacing:.14em;color:#8a8880;
                          text-transform:uppercase">Genlineage</div>
              <h1 style="margin:10px 0 0;font-size:20px;letter-spacing:-.01em">{title}</h1>
            </td></tr>
            <tr><td style="padding:14px 34px 0;font-size:13.5px;line-height:1.65;
                           color:#4a4842;font-family:Helvetica,Arial,sans-serif">{body}</td></tr>
            {btn}
            <tr><td style="padding:26px 34px 28px">
              <div style="border-top:1px solid #eae8e2;padding-top:14px;
                          font-size:11px;color:#8a8880;line-height:1.6">
                Genlineage provenance for generative media. Every asset carries
                its recipe, lineage and signature.
                {f'<br><a href="{_s.APP_URL}" style="color:#e84b0f;text-decoration:none">{site}</a>' if site else ''}
              </div>
            </td></tr>
          </table>
        </td></tr>
      </table></body></html>'''


def send_verify(to: str, url: str) -> bool:
    return send(to, "Verify your Genlineage email", _shell(
        "Confirm your email",
        "<p>Welcome aboard. Confirm this address to secure your account and "
        "unlock everything Genlineage can do.</p>"
        "<p style='color:#8a8880;font-size:12px'>This link expires in 24 hours.</p>",
        url, "Verify email"))


def send_reset(to: str, url: str) -> bool:
    return send(to, "Reset your Genlineage password", _shell(
        "Reset your password",
        "<p>Someone asked to reset the password on this account. If that was "
        "you, set a new one below.</p>"
        "<p style='color:#8a8880;font-size:12px'>This link expires in 30 minutes "
        "and can only be used once. If it wasn't you, ignore this email — nothing "
        "has changed.</p>",
        url, "Set a new password"))


def send_support_ack(to: str, ticket: str, subject: str) -> bool:
    return send(to, f"We got your message ticket {ticket}", _shell(
        "We got your message",
        f"<p>Thanks for reaching out about <b>{subject}</b>.</p>"
        f"<p>Your ticket is <b style='color:#e84b0f'>{ticket}</b> our team replies "
        f"within one business day. Just reply to this email to add anything.</p>"))


def send_support_notify(to: str, ticket: str, subject: str, sender_name: str,
                        sender_email: str, plan_line: str, topic: str,
                        message: str, reply_to: str | None = None) -> bool:
    """Internal ticket notification — same branded shell as every other email."""
    body = (
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' "
        "style='font-size:13px;color:#4a4842;margin-bottom:16px'>"
        f"<tr><td style='padding:3px 0;width:80px;color:#8a8880;vertical-align:top'>From</td>"
        f"<td style='padding:3px 0'>{sender_name} &lt;{sender_email}&gt;{plan_line}</td></tr>"
        f"<tr><td style='padding:3px 0;color:#8a8880;vertical-align:top'>Topic</td>"
        f"<td style='padding:3px 0'>{topic}</td></tr>"
        "</table>"
        "<div style='padding:14px 16px;background:#f4f4f1;border:1px solid #eae8e2;"
        "font-size:13.5px;line-height:1.6;white-space:pre-wrap;"
        f"font-family:Helvetica,Arial,sans-serif'>{message}</div>"
    )
    return send(to, f"[{ticket}] {subject}",
               _shell(f"New ticket — {ticket}", body), reply_to=reply_to)
