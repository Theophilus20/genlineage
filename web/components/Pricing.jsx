"use client";

import Link from "next/link";
import { useState } from "react";

/* Three self-serve tiers with a Monthly/Annual switch, modeled on how X and
   other large subscription products present it: annual shown as the monthly
   equivalent with a modest "SAVE 12%" pill and "billed annually" subtext.
   Visitors aren't subscribers yet, so CTAs say Get started / Subscribe —
   upgrade/downgrade language only exists inside the studio's Billing panel. */

const PLANS = [
  {
    id: "free",
    name: "FREE",
    monthly: 0,
    annualBilled: 0,
    tagline: "For trying the workflow end to end.",
    features: ["3 projects", "4-second shots", "200 commits / month", "Remix DAG + branching", "Signed manifests"],
    cta: "Get started",
  },
  {
    id: "standard",
    name: "STANDARD",
    monthly: 10,
    annualBilled: 105, // 12% off $120
    tagline: "For solo creators shipping regularly.",
    features: ["Unlimited projects", "2,000 commits / month", "Branch cost analytics", "Up to 6-second shots", "Priority generation queue"],
    cta: "Subscribe",
  },
  {
    id: "premium",
    name: "PREMIUM",
    monthly: 25,
    annualBilled: 264, // 12% off $300
    tagline: "Our top tier — for teams running campaigns.",
    features: ["Everything in Standard", "10,000 commits / month", "Quality-gate tuning", "Up to 8-second shots", "Audit exports"],
    cta: "Subscribe",
    popular: true,
  },
];

export const planMath = (p, annual) => {
  if (p.monthly === 0) return { perMonth: 0, billed: 0 };
  if (!annual) return { perMonth: p.monthly, billed: p.monthly };
  return { perMonth: +(p.annualBilled / 12).toFixed(2), billed: p.annualBilled };
};

export default function Pricing() {
  const [cycle, setCycle] = useState("annual");
  const annual = cycle === "annual";

  return (
    <>
      {/* billing switch */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 36 }}>
        <div style={{ display: "inline-flex", border: "1px solid var(--line-strong)", background: "var(--panel)" }}>
          {["monthly", "annual"].map((id) => (
            <button
              key={id}
              onClick={() => setCycle(id)}
              className="mono"
              style={{
                padding: "9px 18px",
                fontSize: 11,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                border: 0,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                background: cycle === id ? "var(--ink)" : "transparent",
                color: cycle === id ? "var(--paper)" : "var(--ink-60)",
              }}
            >
              {id}
              {id === "annual" && (
                <span
                  className="mono"
                  style={{
                    fontSize: 9,
                    padding: "2px 6px",
                    background: cycle === id ? "var(--accent)" : "rgba(245,74,0,0.14)",
                    color: cycle === id ? "#fff" : "var(--accent)",
                    fontWeight: 700,
                  }}
                >
                  SAVE 12%
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 24,
          marginTop: 28,
          alignItems: "stretch",
        }}
      >
        {PLANS.map((p) => {
          const m = planMath(p, annual);
          return (
            <article
              key={p.id}
              className={p.popular ? "tick" : ""}
              style={{
                border: `1px solid ${p.popular ? "var(--accent)" : "var(--line-strong)"}`,
                background: "var(--panel)",
                display: "flex",
                flexDirection: "column",
                boxShadow: p.popular ? "6px 6px 0 rgba(245,74,0,0.18)" : "none",
              }}
            >
              <div style={{ padding: "18px 20px", borderBottom: "1px solid var(--line)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 className="display" style={{ fontSize: 20 }}>{p.name}</h3>
                  {p.popular && <span className="tag fill">Most popular</span>}
                </div>
                <div style={{ marginTop: 14, display: "flex", alignItems: "baseline", gap: 8 }}>
                  <span className="display" style={{ fontSize: 42 }}>
                    ${m.perMonth % 1 === 0 ? m.perMonth : m.perMonth.toFixed(2)}
                  </span>
                  <span className="mono dim" style={{ fontSize: 11 }}>/ month</span>
                </div>
                <p className="mono" style={{ fontSize: 11, marginTop: 6, color: "var(--ink-60)" }}>
                  {p.monthly === 0 ? (
                    "free forever · no card required"
                  ) : annual ? (
                    <>
                      billed annually — <s style={{ opacity: 0.55 }}>${p.monthly * 12}</s>{" "}
                      <b style={{ color: "var(--ok)" }}>${m.billed}/year</b> · save ${p.monthly * 12 - m.billed}
                    </>
                  ) : (
                    "billed monthly · cancel anytime"
                  )}
                </p>
                <p className="dim" style={{ fontSize: 13, marginTop: 12, lineHeight: 1.5 }}>{p.tagline}</p>
              </div>
              <ul className="mono" style={{ listStyle: "none", padding: "16px 20px", display: "grid", gap: 10, fontSize: 12, flex: 1 }}>
                {p.features.map((f) => (
                  <li key={f} style={{ display: "flex", gap: 8 }}>
                    <span style={{ color: "var(--accent)" }}>■</span>
                    <span className="dim">{f}</span>
                  </li>
                ))}
              </ul>
              <div style={{ padding: "0 20px 20px" }}>
                <Link
                  href={p.id === "free" ? "/signup" : `/signup?plan=${p.id}&cycle=${cycle}`}
                  className={`btn${p.popular ? " solid" : ""}`}
                  style={{ justifyContent: "center", width: "100%" }}
                >
                  {p.cta}
                </Link>
              </div>
            </article>
          );
        })}
      </div>

      <p className="mono dim" style={{ fontSize: 11, marginTop: 24 }}>
        Every plan includes the remix DAG, quality gate, and signed manifests.
        Deduplicated commits never count against your allowance.
      </p>
    </>
  );
}
