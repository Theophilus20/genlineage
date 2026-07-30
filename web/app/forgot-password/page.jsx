"use client";

import Link from "next/link";
import { useState } from "react";
import Nav from "../../components/Nav";
import Footer from "../../components/Footer";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!email || !email.includes("@")) {
      setErr("Enter a valid email address.");
      return;
    }
    setErr("");
    await fetch("/api/auth/forgot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }).catch(() => null);
    setSent(true);
  };

  return (
    <>
      <Nav variant="minimal" />
      <main className="rails">
        <section style={{ padding: "72px 24px", display: "grid", placeItems: "center", minHeight: "calc(100vh - var(--nav-h) - 200px)" }}>
          <div className="tick" style={{ border: "1px solid var(--line-strong)", background: "var(--panel)", padding: 32, maxWidth: 460, width: "100%" }}>
            <span className="eyebrow orange">Account recovery</span>
            <h1 className="display" style={{ fontSize: 34, marginTop: 14 }}>
              RESET PASSWORD
            </h1>

            {sent ? (
              <>
                <p className="dim" style={{ fontSize: 14, lineHeight: 1.6, marginTop: 18 }}>
                  If an account exists for <b style={{ color: "var(--ink)" }}>{email}</b>, a
                  password-reset link is on its way. Check your inbox and spam folder.
                </p>
                <Link href="/login" className="btn" style={{ justifyContent: "center", marginTop: 24, width: "100%" }}>
                  Back to log in
                </Link>
              </>
            ) : (
              <>
                <p className="dim" style={{ fontSize: 14, lineHeight: 1.6, marginTop: 18 }}>
                  Enter the email tied to your account and we'll send a link to set a new password.
                </p>
                <div style={{ display: "grid", gap: 8, marginTop: 22 }}>
                  <label htmlFor="email">Email</label>
                  <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@studio.dev" onKeyDown={(e) => e.key === "Enter" && submit()} />
                </div>
                {err && <p className="mono" style={{ fontSize: 12, color: "var(--accent)", marginTop: 12 }}>{err}</p>}
                <button className="btn solid" style={{ justifyContent: "center", width: "100%", marginTop: 20 }} onClick={submit}>
                  Send reset link →
                </button>
                <p className="mono dim" style={{ fontSize: 11.5, textAlign: "center", marginTop: 16 }}>
                  Remembered it? <Link href="/login" style={{ color: "var(--accent)" }}>Log in</Link>
                </p>
              </>
            )}
          </div>
        </section>
        <Footer variant="slim" />
      </main>
    </>
  );
}
