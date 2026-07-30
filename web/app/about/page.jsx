import Link from "next/link";
import Nav from "../../components/Nav";
import Footer from "../../components/Footer";
import Reveal from "../../components/Reveal";

export const metadata = { title: "About - Genlineage" };

const PILLARS = [
  ["Media commits", "Every generated asset is recorded as an immutable commit: the bytes, plus the complete recipe that produced them model, prompt, parameters, seed, parents, and evaluation scores. The asset's own sha256 hash is its permanent address."],
  ["The remix DAG", "Commits reference their parents, so every remix, variation, and re-cut becomes an edge in a directed graph. Any asset traces back to its origin in one walk and branching a campaign only regenerates what actually changed."],
  ["The quality gate", "An evaluator model reviews every output against its spec before it merges. Below threshold, the critique is folded into revised parameters and retried; if a generation path keeps failing, the pipeline fails over automatically."],
  ["Content credentials", "A signed manifest ships beside every merged asset its recipe, its lineage, and an ed25519 signature. Anyone can verify where an asset came from without trusting our word for it."],
];

const PRINCIPLES = [
  ["Provenance is not a feature", "It's the substrate. In a world of infinite generation, the history of an asset is what makes it trustworthy, reusable, and worth paying for."],
  ["Never pay twice", "Content-addressing means identical work is stored once and referenced everywhere. Remix a campaign and unchanged steps cost nothing."],
  ["Fail clearly, recover quietly", "Every rejected generation is kept and logged. Retries and failovers happen automatically but the full record of what was tried is always one click away."],
  ["Verify, don't trust", "Signatures and append-only logs mean our own database is not the source of truth. The ledger is."],
];

export default function About() {
  return (
    <>
      <Nav variant="minimal" />
      <main className="rails">
        {/* hero */}
        <section style={{ padding: "64px 24px 56px", borderBottom: "1px solid var(--line-strong)" }}>
          <span className="eyebrow orange">About Genlineage</span>
          <h1 className="display" style={{ fontSize: "clamp(40px, 8vw, 96px)", marginTop: 20, maxWidth: 900 }}>
            EVERY GENERATION HAS A HISTORY
          </h1>
          <p className="dim" style={{ fontSize: 16, lineHeight: 1.7, maxWidth: 640, marginTop: 24 }}>
            Genlineage is version control for generative media. Teams use it to build and manage AI generation pipelines 
            for images, video, audio, and music. Every generated asset is versioned, 
            evaluated, connected to its lineage, and cryptographically signed. Think of it as Git for AI generated media.
          </p>
        </section>

        {/* the problem */}
        <section style={{ padding: "64px 24px", borderBottom: "1px solid var(--line-strong)" }}>
          <Reveal>
            <span className="eyebrow">Why it exists</span>
            <h2 className="display" style={{ fontSize: "clamp(28px, 4.5vw, 48px)", marginTop: 16, maxWidth: 760 }}>
              GENERATIVE PIPELINES FORGET
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 32, marginTop: 28 }}>
              <p className="dim" style={{ fontSize: 14.5, lineHeight: 1.7 }}>
                A modern campaign touches dozens of generations across multiple models:
                storyboard frames, animated shots, voiceover takes, music beds, final
                cuts. The prompts that produced them live in chat histories. The
                parameters are gone. Which take was approved? Which model made it?
                What did the failed attempts cost?
              </p>
              <p className="dim" style={{ fontSize: 14.5, lineHeight: 1.7 }}>
                Genlineage answers those questions structurally. Every generation is a
                commit with a complete recipe. Every remix is an edge in a graph. Every
                merge passes a quality gate, and every merged asset carries a signed,
                independently verifiable record of where it came from.
              </p>
            </div>
          </Reveal>
        </section>

        {/* what it is */}
        <section style={{ padding: "64px 24px", borderBottom: "1px solid var(--line-strong)" }}>
          <Reveal>
            <span className="eyebrow">What it is</span>
            <h2 className="display" style={{ fontSize: "clamp(28px, 4.5vw, 48px)", marginTop: 16 }}>
              FOUR IDEAS, ONE LEDGER
            </h2>
          </Reveal>
          <div style={{ display: "grid", background: "var(--paper)", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 1, marginTop: 36, border: "1px solid var(--line-strong)", background: "var(--paper)" }}>
            {PILLARS.map(([head, body], i) => (
              <Reveal key={head} delay={i * 70} style={{ background: "var(--panel)" }}>
                <div style={{ padding: "26px 22px", height: "100%" }}>
                  <span className="mono" style={{ fontSize: 10, color: "var(--accent)", letterSpacing: "0.1em" }}>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3 className="display" style={{ fontSize: 22, marginTop: 8 }}>{head}</h3>
                  <p className="dim" style={{ fontSize: 13.5, lineHeight: 1.65, marginTop: 10 }}>{body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* how a run works */}
        <section style={{ padding: "64px 24px", borderBottom: "1px solid var(--line-strong)" }}>
          <Reveal>
            <span className="eyebrow">How a run works</span>
            <h2 className="display" style={{ fontSize: "clamp(28px, 4.5vw, 48px)", marginTop: 16 }}>
              FROM BRIEF TO SIGNED ASSET
            </h2>
            <p className="dim" style={{ fontSize: 14.5, lineHeight: 1.7, maxWidth: 640, marginTop: 20 }}>
              You give the studio a brief. A planning model decomposes it into typed
              steps frames, shots, voiceover, music, final cut each with its own
              spec. Every step is generated, scored by an evaluator against its spec,
              retried or failed over if it misses the bar, then hashed, signed and
              committed to the ledger. The result is not just a folder of outputs:
              it's a graph you can branch, audit, and verify.
            </p>
          </Reveal>
          <div className="cellgrid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", marginTop: 32 }}>
            {[
              ["01", "Plan"],
              ["02", "Generate"],
              ["03", "Evaluate"],
              ["04", "Retry / failover"],
              ["05", "Commit + sign"],
            ].map(([n, k]) => (
              <div className="cell" key={n}>
                <div className="v" style={{ color: n === "04" ? "var(--accent)" : "var(--ink)" }}>{n}</div>
                <div className="k">{k}</div>
              </div>
            ))}
          </div>
        </section>

        {/* principles */}
        <section style={{ padding: "64px 24px", borderBottom: "1px solid var(--line-strong)" }}>
          <Reveal>
            <span className="eyebrow">What we believe</span>
            <h2 className="display" style={{ fontSize: "clamp(28px, 4.5vw, 48px)", marginTop: 16 }}>
              PRINCIPLES
            </h2>
          </Reveal>
          <div style={{ marginTop: 32 }}>
            {PRINCIPLES.map(([head, body], i) => (
              <Reveal key={head} delay={i * 60}>
                <div style={{ display: "grid", gridTemplateColumns: "minmax(200px, 320px) 1fr", gap: 24, padding: "22px 0", borderTop: "1px solid var(--line)" }}>
                  <span className="display" style={{ fontSize: 19 }}>{head}</span>
                  <p className="dim" style={{ fontSize: 14, lineHeight: 1.65 }}>{body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* cta */}
        <section style={{ padding: "72px 24px 88px" }}>
          <Reveal>
            <span className="eyebrow orange">See it yourself</span>
            <h2 className="display" style={{ fontSize: "clamp(32px, 5.5vw, 64px)", marginTop: 14 }}>
              START TRACING
            </h2>
            <div style={{ display: "flex", gap: 12, marginTop: 26, flexWrap: "wrap" }}>
              <Link href="/signup" className="btn solid">Create an account →</Link>
              <Link href="/#pricing" className="btn">View pricing</Link>
            </div>
          </Reveal>
        </section>

        <Footer variant="slim" />
      </main>
    </>
  );
}
