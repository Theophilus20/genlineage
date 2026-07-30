"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Nav from "./Nav";
import Footer from "./Footer";

function FloatingCharacter({ name }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    let raf;
    const onMove = (e) => {
      const x = (e.clientX / window.innerWidth - 0.5) * 16;
      const y = (e.clientY / window.innerHeight - 0.5) * 12;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        el.style.transform = `translate(${x}px, ${y}px)`;
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);
  return (
    <img
      ref={ref}
      src={`/characters/${name}.webp`}
      alt=""
      width={320}
      height={320}
      style={{ maxWidth: "72%", height: "auto", transition: "transform 0.2s ease-out" }}
    />
  );
}

function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden style={{ flexShrink: 0 }}>
      <path fill="#4285F4" d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z"/>
      <path fill="#34A853" d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z"/>
      <path fill="#FBBC05" d="M11.69 28.18C11.25 26.86 11 25.45 11 24s.25-2.86.69-4.18v-5.7H4.34C2.85 17.09 2 20.45 2 24s.85 6.91 2.34 9.88l7.35-5.7z"/>
      <path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z"/>
    </svg>
  );
}

function passwordStrength(pw) {
  if (!pw) return null;
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  if (score <= 2) return { label: "Weak", color: "var(--accent)", pct: 33 };
  if (score <= 3) return { label: "Fair", color: "var(--warn)", pct: 66 };
  return { label: "Strong", color: "var(--ok)", pct: 100 };
}

function EyeIcon({ open }) {
  return open ? (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" /><circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function PasswordField({ id, label, value, onChange, onEnter, extra }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <label htmlFor={id}>{label}</label>
      <div style={{ position: "relative" }}>
        <input
          id={id}
          type={show ? "text" : "password"}
          value={value}
          onChange={onChange}
          placeholder="********"
          style={{ paddingRight: 42 }}
          onKeyDown={(e) => e.key === "Enter" && onEnter && onEnter()}
        />
        <button
          type="button"
          aria-label={show ? "Hide password" : "Show password"}
          onClick={() => setShow((v) => !v)}
          className="dim"
          style={{
            position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
            background: "transparent", border: 0, display: "grid", placeItems: "center", padding: 4,
          }}
        >
          <EyeIcon open={show} />
        </button>
      </div>
      {extra}
    </div>
  );
}

const PLAN_PRICING = {
  standard: { name: "Standard", monthly: 10, annual: 105 },
  premium: { name: "Premium", monthly: 25, annual: 264 },
};

const planLabel = (id, cycle) => {
  const p = PLAN_PRICING[id];
  if (!p) return null;
  return cycle === "annual" || cycle === "yearly"
    ? `${p.name} — $${p.annual}/year, billed annually (12% off)`
    : `${p.name} — $${p.monthly}/month`;
};

export default function AuthPanel({ mode }) {
  const isSignup = mode === "signup";
  const character = isSignup ? "blob" : "snow";
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [agree, setAgree] = useState(false);
  const [err, setErr] = useState("");
  const [plan, setPlan] = useState(null);
  const [cycle, setCycle] = useState("monthly");

  // preserve plan intent from pricing CTAs (?plan=studio&cycle=yearly)
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const p = q.get("plan");
    if (p && PLAN_PRICING[p]) setPlan(p);
    const c = q.get("cycle");
    if (c === "monthly" || c === "annual" || c === "yearly") {
      const norm = c === "yearly" ? "annual" : c;
      setCycle(norm);
      localStorage.setItem("genlineage.cycle", norm);
    }
  }, []);

  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email || !password || (isSignup && !name)) {
      setErr("Fill in every field to continue.");
      return;
    }
    if (isSignup && password.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }
    if (isSignup && password !== confirm) {
      setErr("Passwords do not match.");
      return;
    }
    if (isSignup && !agree) {
      setErr("Please accept the Terms and Privacy Policy.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const r = await fetch(`/api/auth/${isSignup ? "register" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          isSignup
            ? { name, email, password, plan: plan || undefined, cycle }
            : { email, password }
        ),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setErr(data.detail || "Something went wrong — try again.");
        return;
      }
      localStorage.setItem("genlineage.user", JSON.stringify(data));
      router.push(plan ? `/studio?intent=${plan}&cycle=${cycle}` : "/studio");
    } catch {
      setErr("Can't reach the server — is the backend running?");
    } finally {
      setBusy(false);
    }
  };

  const [googleReady, setGoogleReady] = useState(false);

  useEffect(() => {
    fetch("/api/auth/google/status")
      .then((r) => r.json())
      .then((d) => setGoogleReady(!!d.enabled))
      .catch(() => setGoogleReady(false));
  }, []);

  // surface errors bounced back from the OAuth callback
  useEffect(() => {
    const e = new URLSearchParams(window.location.search).get("error");
    if (e === "google_cancelled") setErr("Google sign-in was cancelled.");
    else if (e) setErr("Google sign-in failed — try email instead.");
  }, []);

  const googleAuth = () => {
    if (!googleReady) {
      setErr("Google sign-in isn't configured on this server — use email.");
      return;
    }
    // full-page redirect to Google's consent screen
    window.location.href = "/api/auth/google/start"; // continuing implies ToS/Privacy consent
  };

  return (
    <>
      <Nav variant="minimal" />
      <main className="rails" style={{ display: "grid", alignContent: "start" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            minHeight: "calc(100vh - var(--nav-h))",
          }}
        >
          {/* character side */}
          <section
            style={{
              borderRight: "1px solid var(--line-strong)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              padding: "40px 32px",
            }}
          >
            <span className="eyebrow orange">{isSignup ? "New lineage" : "Welcome back"}</span>
            <div style={{ display: "grid", placeItems: "center", padding: "24px 0" }}>
              <FloatingCharacter name={character} />
            </div>
            <div>
              <h1 className="display" style={{ fontSize: "clamp(36px, 5vw, 60px)" }}>
                {isSignup ? "START_TRACING" : "LOG_IN"}
              </h1>
              <p className="dim" style={{ marginTop: 12, fontSize: 14, maxWidth: 380, lineHeight: 1.6 }}>
                {isSignup
                  ? "Create an account and every asset you generate gets a commit, a lineage, and a signature."
                  : "Your projects, branches and signed manifests are where you left them."}
              </p>
            </div>
          </section>

          {/* form side */}
          <section style={{ padding: "40px 32px", display: "grid", alignContent: "center" }}>
            <div className="tick" style={{ border: "1px solid var(--line-strong)", background: "var(--panel)", padding: 28, maxWidth: 440, width: "100%", justifySelf: "center" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                <span className="tag fill" style={{ flexShrink: 0 }}>{isSignup ? "Sign up" : "Log in"}</span>
                {plan && (
                  <span
                    className="tag"
                    title={planLabel(plan, cycle)}
                    style={{ borderColor: "var(--accent)", color: "var(--accent)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", minWidth: 0 }}
                  >
                    Plan: {planLabel(plan, cycle)}
                  </span>
                )}
              </div>

              <div style={{ display: "grid", gap: 18, marginTop: 24 }}>
                {isSignup && (
                  <div style={{ display: "grid", gap: 8 }}>
                    <label htmlFor="name">Name</label>
                    <input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada Lovelace" />
                  </div>
                )}
                <div style={{ display: "grid", gap: 8 }}>
                  <label htmlFor="email">Email</label>
                  <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@studio.dev" />
                </div>
                <PasswordField
                  id="password"
                  label="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onEnter={!isSignup ? submit : undefined}
                  extra={
                    isSignup ? (
                      (() => {
                        const st = passwordStrength(password);
                        return (
                          <div style={{ display: "grid", gap: 5 }}>
                            <div style={{ height: 4, background: "var(--line)" }}>
                              {st && <div style={{ height: "100%", width: `${st.pct}%`, background: st.color, transition: "width 0.25s, background 0.25s" }} />}
                            </div>
                            <span className="mono" style={{ fontSize: 10, color: st ? st.color : "var(--ink-60)" }}>
                              {st ? `${st.label} password` : "Use 12+ characters with numbers, symbols and mixed case."}
                            </span>
                          </div>
                        );
                      })()
                    ) : (
                      <Link href="/forgot-password" className="mono" style={{ fontSize: 11, color: "var(--accent)", justifySelf: "start" }}>
                        Forgot password?
                      </Link>
                    )
                  }
                />
                {isSignup && (
                  <PasswordField
                    id="confirm"
                    label="Confirm password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    onEnter={submit}
                    extra={
                      confirm && password !== confirm ? (
                        <span className="mono" style={{ fontSize: 10.5, color: "var(--accent)" }}>Passwords do not match</span>
                      ) : confirm && password === confirm ? (
                        <span className="mono" style={{ fontSize: 10.5, color: "var(--ok)" }}>✓ Passwords match</span>
                      ) : null
                    }
                  />
                )}

                {isSignup && (
                  <label className="mono" style={{ display: "flex", gap: 8, fontSize: 11, textTransform: "none", letterSpacing: 0, color: "var(--ink-60)", cursor: "pointer", alignItems: "flex-start", lineHeight: 1.5 }}>
                    <input type="checkbox" required checked={agree} onChange={(e) => setAgree(e.target.checked)} style={{ width: "auto", marginTop: 2 }} />
                    <span>
                      I agree to the{" "}
                      <Link href="/terms" style={{ color: "var(--accent)" }}>Terms of Service</Link> and{" "}
                      <Link href="/privacy" style={{ color: "var(--accent)" }}>Privacy Policy</Link>.
                    </span>
                  </label>
                )}

                {err && (
                  <p className="mono" style={{ fontSize: 12, color: "var(--accent)" }}>{err}</p>
                )}
                <button className="btn solid" style={{ justifyContent: "center" }} onClick={submit} disabled={busy}>
                  {busy ? "One moment…" : isSignup ? "Create account →" : "Enter the studio →"}
                </button>

                {/* social auth below the primary form, like the big providers */}
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ flex: 1, height: 1, background: "var(--line-strong)" }} />
                  <span className="mono dim" style={{ fontSize: 10, letterSpacing: "0.08em" }}>OR</span>
                  <span style={{ flex: 1, height: 1, background: "var(--line-strong)" }} />
                </div>
                <button className="btn" style={{ justifyContent: "center", background: "#fdfdfb" }} onClick={googleAuth}>
                  <GoogleMark /> {isSignup ? "Sign up with Google" : "Sign in with Google"}
                </button>

                <p className="mono dim" style={{ fontSize: 11.5, textAlign: "center" }}>
                  {isSignup ? (
                    <>Already tracing? <Link href="/login" style={{ color: "var(--accent)" }}>Log in</Link></>
                  ) : (
                    <>New here? <Link href="/signup" style={{ color: "var(--accent)" }}>Create an account</Link></>
                  )}
                </p>
              </div>
            </div>
          </section>
        </div>
        <Footer variant="slim" />
      </main>
    </>
  );
}
