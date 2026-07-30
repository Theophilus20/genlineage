import Link from "next/link";
import Nav from "../components/Nav";
import Footer from "../components/Footer";
import Pricing from "../components/Pricing";
import Reveal from "../components/Reveal";
import ScrollBot from "../components/ScrollBot";

const FEATURES = [
  {
    tag: "Ledger",
    name: "MEDIA COMMIT",
    desc: "Every output is an immutable record asset plus its full recipe: model, prompt, params, seed, parents, and eval scores. The asset's sha256 is its address.",
    cells: [
      ["sha256", "Object key"],
      ["100%", "Reproducible"],
      ["0", "Copies stored twice"],
      ["∞", "Retention"],
    ],
  },
  {
    tag: "Graph",
    name: "REMIX DAG",
    desc: "Commits reference parents; every remix is an edge. Branch a campaign, swap one prompt, and only the changed nodes regenerate the rest dedup-reference the store.",
    cells: [
      ["O(1)", "Trace to origin"],
      ["Branches", "Cheap by design"],
      ["Diff", "Any two nodes"],
      ["JSONL", "Append-only log"],
    ],
  },
  {
    tag: "Agentic",
    name: "QUALITY GATE",
    desc: "An evaluator model critiques every output against its spec before merge. Below threshold → retry with revised params. Still failing → automatic provider failover.",
    cells: [
      ["7.0/10", "Merge threshold"],
      ["Auto", "Retry + failover"],
      ["JSON", "Scored rubric"],
      ["Kept", "Every reject logged"],
    ],
  },
  {
    tag: "Trust",
    name: "CONTENT CREDENTIALS",
    desc: "A signed C2PA-style manifest lives beside every merged asset recipe, lineage, and an ed25519 signature anyone can verify without trusting our database.",
    cells: [
      ["ed25519", "Signature"],
      ["Durable", "Beside every asset"],
      ["Public", "Verify endpoint"],
      ["Tamper", "Evident by design"],
    ],
  },
];

const PHASES = [
  ["01", "PLAN", "A planning model decomposes the brief into typed pipeline steps script, frames, shots, voiceover, final cut each with its own spec and dependencies."],
  ["02", "GENERATE", "Each step is routed by modality through a single generation abstraction. One interface, many backends, the same spec everywhere."],
  ["03", "EVALUATE", "A vision model scores the output against the step's spec and returns a JSON rubric: score, critique, parameter suggestions."],
  ["04", "RETRY / FAILOVER", "Failed the gate? The critique is folded into revised params and retried. Still failing? The pipeline fails over to a backup path with the same spec."],
  ["05", "COMMIT", "Hash the bytes, sign the manifest, upload to the content-addressed ledger, append the DAG log. The asset now has a history."],
];

const CAPABILITIES = [
  ["Multi-modal", "Image, video, voice and music generation orchestrated in one pipeline, each step typed and tracked."],
  ["Resilient by design", "If a primary generation path stalls or errors, the pipeline fails over to a backup with the same spec no run left hanging on a single backend."],
  ["Cost-aware", "Every commit records its own generation cost. Remixes dedup unchanged steps, so branching a campaign doesn't re-pay for what didn't change."],
  ["Verifiable", "A signed manifest ships beside every asset. Anyone can verify lineage and integrity without trusting our database."],
];

export default function Landing() {
  return (
    <>
      <Nav />
      <main className="rails">
        {/* ---------------- HERO ---------------- */}
        <section
          style={{
            position: "relative",
            padding: "56px 24px 0",
            borderBottom: "1px solid var(--line-strong)",
            overflow: "hidden",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <span className="eyebrow orange">Git for generative media</span>
            <span className="tag">v2 — production ready</span>
          </div>

          <h1
            className="display"
            style={{
              fontSize: "clamp(56px, 12.5vw, 168px)",
              marginTop: 28,
              position: "relative",
              zIndex: 2,
            }}
          >
            GEN_
            <br />
            LINEAGE
          </h1>

          {/* the character sits in the grid, reacting to scroll */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              marginTop: "clamp(-120px, -9vw, -40px)",
              position: "relative",
              zIndex: 1,
            }}
          >
            <ScrollBot name="robot" frames={63} size={440} />
          </div>

          <div style={{ padding: "8px 0 40px" }}>
            <p className="dim" style={{ maxWidth: 420, fontSize: 15, lineHeight: 1.6 }}>
              Every generation has a history. Genlineage records each output as a
              content-addressed commit, gates it through an agentic evaluator, and
              signs its provenance — so any asset traces back to origin.
            </p>
          </div>
        </section>

        {/* ---------------- STATS STRIP ---------------- */}
        <section style={{ padding: "0" }}>
          <div className="cellgrid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", border: 0, borderBottom: "1px solid var(--line-strong)" }}>
            {[
              ["5", "Pipeline phases"],
              ["3+", "Providers, one spec"],
              ["7.0", "Quality gate min"],
              ["sha256", "Every address"],
              ["ed25519", "Every manifest"],
            ].map(([v, k]) => (
              <div className="cell" key={k} style={{ background: "var(--paper)" }}>
                <div className="v" style={{ color: v === "7.0" ? "var(--accent)" : "var(--ink)" }}>{v}</div>
                <div className="k">{k}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------- LEDGER / FEATURES ---------------- */}
        <section id="ledger" style={{ padding: "72px 24px" }}>
          <Reveal>
            <span className="eyebrow">The ledger</span>
            <h2 className="display" style={{ fontSize: "clamp(32px, 5vw, 56px)", marginTop: 16, maxWidth: 720 }}>
              EVERY GENERATION HAS A HISTORY
            </h2>
          </Reveal>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: 32,
              marginTop: 48,
            }}
          >
            {FEATURES.map((f, i) => (
              <Reveal key={f.name} delay={i * 90}>
                <article className="tick" style={{ border: "1px solid var(--line-strong)", background: "var(--panel)" }}>
                  <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--line)" }}>
                    <span className="tag">{f.tag}</span>
                    <h3 className="display" style={{ fontSize: 24, marginTop: 14 }}>{f.name}</h3>
                    <p className="dim" style={{ fontSize: 13.5, lineHeight: 1.6, marginTop: 10 }}>{f.desc}</p>
                  </div>
                  <div className="cellgrid" style={{ gridTemplateColumns: "1fr 1fr", border: 0 }}>
                    {f.cells.map(([v, k]) => (
                      <div className="cell" key={k}>
                        <div className="v" style={{ fontSize: 16 }}>{v}</div>
                        <div className="k">{k}</div>
                      </div>
                    ))}
                  </div>
                </article>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ---------------- PIPELINE PHASES ---------------- */}
        <section id="pipeline" className="hairline-top" style={{ padding: "72px 24px" }}>
          <Reveal>
            <span className="eyebrow">The pipeline</span>
            <h2 className="display" style={{ fontSize: "clamp(32px, 5vw, 56px)", marginTop: 16 }}>
              BRIEF → SIGNED ASSET
            </h2>
          </Reveal>
          <div style={{ marginTop: 40 }}>
            {PHASES.map(([n, name, desc], i) => (
              <Reveal key={n} delay={i * 60}>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "80px 240px 1fr",
                    gap: 24,
                    padding: "22px 0",
                    borderTop: "1px solid var(--line)",
                    alignItems: "baseline",
                  }}
                >
                  <span className="display" style={{ fontSize: 28, color: i === 3 ? "var(--accent)" : "var(--ink-32)" }}>{n}</span>
                  <span className="display" style={{ fontSize: 20 }}>{name}</span>
                  <p className="dim" style={{ fontSize: 14, lineHeight: 1.6 }}>{desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ---------------- WHY GENLINEAGE ---------------- */}
        <section id="why" className="hairline-top" style={{ padding: "72px 24px" }}>
          <Reveal>
            <span className="eyebrow">Why teams choose it</span>
            <h2 className="display" style={{ fontSize: "clamp(32px, 5vw, 56px)", marginTop: 16 }}>
              BUILT FOR PIPELINES<br />THAT SHIP
            </h2>
          </Reveal>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: 1,
              marginTop: 40,
              border: "1px solid var(--line-strong)",
              background: "var(--line-strong)",
            }}
          >
            {CAPABILITIES.map(([head, body], i) => (
              <Reveal key={head} delay={i * 80} style={{ background: "var(--panel)" }}>
                <div style={{ padding: "26px 22px", height: "100%" }}>
                  <span className="display" style={{ fontSize: 22 }}>{head}</span>
                  <p className="dim" style={{ fontSize: 13.5, lineHeight: 1.6, marginTop: 10 }}>{body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ---------------- PRICING ---------------- */}
        <section id="pricing" className="hairline-top" style={{ padding: "72px 24px" }}>
          <Reveal>
            <span className="eyebrow">Pricing</span>
            <h2 className="display" style={{ fontSize: "clamp(32px, 5vw, 56px)", marginTop: 16 }}>
              SIMPLE, COMMIT-BASED
            </h2>
            <p className="dim" style={{ marginTop: 12, maxWidth: 520, fontSize: 14, lineHeight: 1.6 }}>
              Start free. Upgrade as your pipelines grow. Deduplicated commits are 
              only stored once, so branching stays affordable.
            </p>
          </Reveal>
          <Reveal delay={100}>
            <Pricing />
          </Reveal>
        </section>

        {/* ---------------- CTA ---------------- */}
        <section className="hairline-top" style={{ padding: "80px 24px 96px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
            <Reveal>
              <span className="eyebrow orange">Ready to trace your pipeline?</span>
              <h2 className="display" style={{ fontSize: "clamp(36px, 6vw, 72px)", marginTop: 14 }}>
                COMMIT<br />EVERYTHING
              </h2>
            </Reveal>
            <Reveal delay={120} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <Link href="/signup" className="btn solid" style={{ justifyContent: "center" }}>Create an account</Link>
              <Link href="/login" className="btn" style={{ justifyContent: "center" }}>Log in</Link>
            </Reveal>
          </div>
        </section>

        <Footer />
      </main>
    </>
  );
}
