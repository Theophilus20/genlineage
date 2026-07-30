import PageShell from "../../components/PageShell";

const SECTIONS = [
  ["1. What we collect", "Account details (name, email), the briefs and parameters you submit, generated assets and their recipes, and standard usage telemetry needed to operate the Service. We do not sell your data."],
  ["2. How we use it", "To run your pipelines, store your ledger, evaluate outputs through the quality gate, provide support, and improve reliability. Prompts and assets are used to fulfill your requests — not to train our own foundation models."],
  ["3. Third-party processing", "Briefs and intermediate assets are transmitted to the generation and evaluation providers you route to (e.g. fal.ai, Replicate, ElevenLabs, Gemini) solely to produce your requested outputs. Each provider processes data under its own policy."],
  ["4. Storage & retention", "Assets, manifests, and DAG logs are stored in your configured content-addressed bucket (Backblaze B2 or local). Rejected generations are written to a failures area with a short lifecycle rule and auto-deleted. You can export or delete your data at any time."],
  ["5. Security", "Provenance manifests are signed with ed25519 keys. Data in transit is encrypted. Access to production systems is restricted and logged. Report vulnerabilities to genlineageai@gmail.com."],
  ["6. Your rights", "You may access, correct, export, or delete your personal data. Depending on your region, you may have additional rights under GDPR or CCPA. Contact us to exercise them."],
  ["7. Cookies", "We use essential cookies for authentication and preferences. We do not use third-party advertising trackers."],
  ["8. Contact", "Questions about this policy? Email genlineageai@gmail.com or use the support form."],
];

export default function Privacy() {
  return (
    <PageShell eyebrow="Legal" title="PRIVACY POLICY">
      <p className="mono dim" style={{ fontSize: 12 }}>Last updated: January 2026</p>
      <div style={{ display: "grid", gap: 28, marginTop: 28 }}>
        {SECTIONS.map(([h, body]) => (
          <div key={h}>
            <h2 className="mono" style={{ fontSize: 15, fontWeight: 700, marginBottom: 8 }}>{h}</h2>
            <p className="dim" style={{ fontSize: 14, lineHeight: 1.7 }}>{body}</p>
          </div>
        ))}
      </div>
    </PageShell>
  );
}
