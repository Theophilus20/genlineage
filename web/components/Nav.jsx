"use client";

import Link from "next/link";

export default function Nav({ variant = "landing" }) {
  const minimal = variant === "minimal";
  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: "var(--paper)",
        borderBottom: "1px solid var(--line-strong)",
      }}
    >
      <div
        className="rails"
        style={{
          minHeight: 0,
          height: "var(--nav-h)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
        }}
      >
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img src="/logo.png" alt="" style={{ width: 26, height: 26, objectFit: "contain" }} />
          <span className="mono" style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.04em" }}>
            GEN<span style={{ color: "var(--accent)" }}>_</span>LINEAGE
          </span>
        </Link>

        {!minimal && (
          <nav className="mono" style={{ display: "flex", gap: 28, fontSize: 12 }}>
            <span className="gl-navlinks" style={{ display: "inline-flex", gap: "inherit" }}>
              <a href="/#pipeline" className="dim">Pipeline</a>
              <a href="/#ledger" className="dim">Ledger</a>
              <a href="/#pricing" className="dim">Pricing</a>
            </span>
          </nav>
        )}

        {minimal ? (
          <Link href="/" className="mono dim" style={{ fontSize: 12 }}>
            &larr; Back to home
          </Link>
        ) : (
          <div style={{ display: "flex", gap: 10 }}>
            <Link href="/login" className="btn" style={{ padding: "8px 14px" }}>
              Log in
            </Link>
            <Link href="/signup" className="btn solid" style={{ padding: "8px 14px" }}>
              Start tracing
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
