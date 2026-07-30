import Link from "next/link";
import Nav from "./Nav";
import Footer from "./Footer";

export default function PageShell({ eyebrow, title, children, maxWidth = 760 }) {
  return (
    <>
      <Nav variant="minimal" />
      <main className="rails">
        <section style={{ padding: "56px 24px 72px" }}>
          <div style={{ maxWidth, margin: "0 auto" }}>
            <span className="eyebrow orange">{eyebrow}</span>
            <h1 className="display" style={{ fontSize: "clamp(36px, 6vw, 68px)", marginTop: 18 }}>
              {title}
            </h1>
            <div style={{ marginTop: 32 }}>{children}</div>
          </div>
        </section>
        <Footer variant="slim" />
      </main>
    </>
  );
}
