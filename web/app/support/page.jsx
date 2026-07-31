"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Nav from "../../components/Nav";
import Footer from "../../components/Footer";

const TOPICS = ["General question", "Billing", "Bug report", "Feature request", "Security disclosure"];

export default function Support() {
  const [form, setForm] = useState({ name: "", email: "", topic: TOPICS[0], message: "" });
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const [busy, setBusy] = useState(false);
  const [ticket, setTicket] = useState("");
  const [siteKey, setSiteKey] = useState(null);

  useEffect(() => {
    fetch("/api/turnstile").then((r) => r.json()).then((d) => setSiteKey(d.site_key || null)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!siteKey) return;
    let stop = false, tries = 0;
    const mount = () => {
      if (stop) return;
      const box = document.getElementById("ts-support");
      if (!box || !window.turnstile) { if (tries++ < 40) setTimeout(mount, 100); return; }
      if (box.dataset.rendered === "1") return;
      box.dataset.rendered = "1";
      try { window.turnstile.render(box, { sitekey: siteKey, theme: "light" }); }
      catch (e) { box.dataset.rendered = ""; console.error("[turnstile]", e); }
    };
    if (window.turnstile) { mount(); return () => { stop = true; }; }
    const sc = document.createElement("script");
    sc.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    sc.async = true; sc.defer = true; sc.onload = mount;
    document.head.appendChild(sc);
    return () => { stop = true; };
  }, [siteKey]);

  const submit = async () => {
    if (!form.name || !form.email.includes("@") || !form.message.trim()) {
      setErr("Name, a valid email, and a message are required.");
      return;
    }
    setErr("");
    setBusy(true);
    try {
      const token = window.turnstile ? window.turnstile.getResponse() : null;
      const r = await fetch("/api/support", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name, email: form.email, topic: form.topic,
          subject: form.topic, message: form.message, turnstile_token: token,
        }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || "Couldn't send your message.");
      setTicket(d.ticket || "");
      setSent(true);
    } catch (e) {
      setErr(String(e.message || "Couldn't send your message."));
      if (window.turnstile) window.turnstile.reset();
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Nav variant="minimal" />
      <main className="rails">
        <section style={{ padding: "56px 24px 72px" }}>
          <div style={{ maxWidth: 900, margin: "0 auto" }}>
            <span className="eyebrow orange">We're here to help</span>
            <h1 className="display" style={{ fontSize: "clamp(36px, 6vw, 68px)", marginTop: 18 }}>
              CUSTOMER SUPPORT
            </h1>
            <p className="dim" style={{ fontSize: 15, lineHeight: 1.6, marginTop: 16, maxWidth: 560 }}>
              Questions about pipelines, provenance, billing or the API? Send us a note
              and the team gets back within one business day.
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 32, marginTop: 44, alignItems: "start" }}>
              {/* contact channels */}
              <div className="cellgrid" style={{ gridTemplateColumns: "1fr" }}>
                {[
                  ["Email", "genlineageai@gmail.com"],
                  ["Response time", "< 1 business day"],
                  ["Security", "genlineageai@gmail.com"],
                  ["Status page", "status.genlineage.dev"],
                ].map(([k, v]) => (
                  <div className="cell" key={k}>
                    <div className="k">{k}</div>
                    <div className="v" style={{ fontSize: 14, marginTop: 4 }}>{v}</div>
                  </div>
                ))}
              </div>

              {/* form */}
              <div className="tick" style={{ border: "1px solid var(--line-strong)", background: "var(--panel)", padding: 26 }}>
                {sent ? (
                  <div style={{ display: "grid", placeItems: "center", padding: "28px 0", textAlign: "center" }}>
                    <div className="display" style={{ fontSize: 30, color: "var(--ok)" }}>✓ SENT</div>
                    <p className="dim" style={{ fontSize: 14, marginTop: 12, lineHeight: 1.6, maxWidth: 340 }}>
                      Thanks, {form.name.split(" ")[0]}. Your ticket {ticket && <b style={{ color: "var(--ink)" }}>{ticket}</b>} is in the queue we'll reply
                      to <b style={{ color: "var(--ink)" }}>{form.email}</b> shortly.
                    </p>
                    <button className="btn" style={{ marginTop: 20 }} onClick={() => { setSent(false); setForm({ name: "", email: "", topic: TOPICS[0], message: "" }); }}>
                      Send another
                    </button>
                  </div>
                ) : (
                  <div style={{ display: "grid", gap: 16 }}>
                    <span className="tag fill">New ticket</span>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                      <div style={{ display: "grid", gap: 6 }}>
                        <label htmlFor="s-name">Name</label>
                        <input id="s-name" value={form.name} onChange={set("name")} placeholder="Ada Lovelace" />
                      </div>
                      <div style={{ display: "grid", gap: 6 }}>
                        <label htmlFor="s-email">Email</label>
                        <input id="s-email" type="email" value={form.email} onChange={set("email")} placeholder="you@studio.dev" />
                      </div>
                    </div>
                    <div style={{ display: "grid", gap: 6 }}>
                      <label htmlFor="s-topic">Topic</label>
                      <select id="s-topic" value={form.topic} onChange={set("topic")}>
                        {TOPICS.map((t) => <option key={t}>{t}</option>)}
                      </select>
                    </div>
                    <div style={{ display: "grid", gap: 6 }}>
                      <label htmlFor="s-msg">Message</label>
                      <textarea id="s-msg" rows={5} value={form.message} onChange={set("message")} placeholder="Tell us what's going on…" />
                    </div>
                    {err && <p className="mono" style={{ fontSize: 12, color: "var(--accent)" }}>{err}</p>}
                    <div id="ts-support" style={{ minHeight: 65 }} />
                    <button className="btn solid" style={{ justifyContent: "center" }} onClick={submit} disabled={busy}>
                      Submit ticket →
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>
        <Footer variant="slim" />
      </main>
    </>
  );
}
