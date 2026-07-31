"use client";

import Link from "next/link";

const COLUMNS = [
  {
    head: "Product",
    links: [
      ["Pipeline", "/#pipeline"],
      ["Ledger", "/#ledger"],
      ["Why Genlineage", "/#why"],
    ],
  },
  {
    head: "Company",
    links: [
      ["About", "/about"],
      ["Support", "/support"],
    ],
  },
  {
    head: "Legal",
    links: [
      ["Terms of Service", "/terms"],
      ["Privacy Policy", "/privacy"],
    ],
  },
];

const SOCIALS = [
  {
    name: "X",
    href: "https://x.com/genlineageai",
    path: "M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z",
  },
  {
    name: "Instagram",
    href: "https://www.instagram.com/genlineageai",
    path: "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0 3.678a6.159 6.159 0 100 12.318 6.159 6.159 0 000-12.318zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z",
  },
  {
    name: "Facebook",
    href: "",
    path: "M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z",
  },
];

function SocialLinks() {
  return (
    <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
      {SOCIALS.map((s) => (
        <a
          key={s.name}
          href={s.href}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Genlineage on ${s.name}`}
          className="dim"
          style={{ display: "inline-flex", padding: 4, border: "1px solid var(--line-strong)", background: "var(--panel)" }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d={s.path} />
          </svg>
        </a>
      ))}
    </div>
  );
}

export default function Footer({ variant = "full" }) {
  const year = new Date().getFullYear();

  /* slim: single legal bar for auth/legal/support pages —
     the full column footer lives on the landing page only */
  if (variant === "slim") {
    return (
      <footer
        className="hairline-top mono dim"
        style={{
          padding: "18px 24px",
          fontSize: 11,
          display: "flex",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 10,
          background: "var(--paper)",
        }}
      >
        <span>© {year} Genlineage Labs, Inc. All rights reserved.</span>
        <span style={{ display: "flex", gap: 18, alignItems: "center" }}>
          <Link href="/terms">Terms</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/support">Support</Link>
          <SocialLinks />
        </span>
      </footer>
    );
  }

  return (
    <footer className="hairline-top" style={{ background: "var(--paper)" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.4fr repeat(3, 1fr)",
          gap: 32,
          padding: "44px 24px 36px",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <img src="/logo.png" alt="" style={{ width: 26, height: 26, objectFit: "contain" }} />
          <span className="mono" style={{ fontSize: 13, fontWeight: 700, lineHeight: "22px" }}>
            GEN<span style={{ color: "var(--accent)" }}>_</span>LINEAGE
          </span>
        </div>

        {COLUMNS.map((col) => (
          <div key={col.head}>
            <div className="mono" style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--ink-60)", marginBottom: 14 }}>
              {col.head}
            </div>
            <div style={{ display: "grid", gap: 10 }}>
              {col.links.map(([label, href]) => (
                <Link key={label} href={href} className="mono dim" style={{ fontSize: 12.5 }}>
                  {label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div
        className="mono dim hairline-top"
        style={{
          padding: "16px 24px",
          fontSize: 11,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <span>© {year} Genlineage Labs, Inc. All rights reserved.</span>
        <SocialLinks />
      </div>
    </footer>
  );
}
