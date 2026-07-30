"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function Eye({ on }) {
  return on ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 7 10 7a13.2 13.2 0 0 1-1.67 2.4M6.6 6.6A13.3 13.3 0 0 0 2 11s3.5 7 10 7a9 9 0 0 0 4-.9"/><path d="m2 2 20 20"/></svg>
  );
}

function Field({ value, onChange, placeholder }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <input type={show ? "text" : "password"} value={value} onChange={onChange} placeholder={placeholder}
        style={{ width: "100%", fontSize: 13, padding: "11px 40px 11px 12px", border: "1px solid #d8d6cf", boxSizing: "border-box" }} />
      <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide" : "Show"}
        style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: 0, color: "#8a8880", cursor: "pointer", padding: 4, display: "flex" }}>
        <Eye on={show} />
      </button>
    </div>
  );
}

function ResetForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") || "";
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (pw.length < 8) return setMsg("Password must be at least 8 characters.");
    if (pw !== pw2) return setMsg("Passwords don't match.");
    setBusy(true); setMsg("");
    const r = await fetch("/api/auth/reset", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, password: pw }),
    });
    const d = await r.json().catch(() => ({}));
    setBusy(false);
    if (!r.ok) return setMsg(d.detail || "This link is invalid or expired — request a new one.");
    setOk(true);
    setMsg("Password updated. Redirecting you to sign in…");
    setTimeout(() => router.push("/login"), 1600);
  };

  return (
    <main className="mono" style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#e9e8e3", padding: 16 }}>
      <form onSubmit={submit} style={{ width: 360, maxWidth: "100%", display: "grid", gap: 14, justifyItems: "center", textAlign: "center", border: "1px solid #d8d6cf", padding: 30, background: "#fdfdfb" }}>
        <img src="/logo.png" alt="" style={{ width: 40, height: 40, objectFit: "contain" }} />
        <b style={{ fontSize: 16 }}>Set a new password</b>
        <div style={{ width: "100%", display: "grid", gap: 12, textAlign: "left" }}>
          <Field value={pw} onChange={(e) => setPw(e.target.value)} placeholder="New password" />
          <Field value={pw2} onChange={(e) => setPw2(e.target.value)} placeholder="Repeat new password" />
        </div>
        {msg && <p style={{ fontSize: 11.5, color: ok ? "#2e7d32" : "#e84b0f", lineHeight: 1.5, margin: 0 }}>{msg}</p>}
        <button disabled={busy || ok} style={{ width: "100%", padding: "12px", background: "#111110", color: "#fff", border: 0, fontSize: 12, cursor: busy ? "default" : "pointer", letterSpacing: "0.04em" }}>
          {busy ? "Saving…" : ok ? "Done" : "Update password"}
        </button>
      </form>
    </main>
  );
}

export default function ResetPage() {
  return <Suspense fallback={null}><ResetForm /></Suspense>;
}
