import PageShell from "../../components/PageShell";

const SECTIONS = [
  ["1. Acceptance of terms", "By creating an account or using Genlineage (the \"Service\"), you agree to these Terms of Service. If you are using the Service on behalf of an organization, you represent that you have authority to bind that organization."],
  ["2. The service", "Genlineage provides version control, provenance tracking, and orchestration for generative-media pipelines. Generated assets, their recipes, and signed manifests are stored in your content-addressed ledger. You retain ownership of the briefs you submit and the assets your pipelines produce."],
  ["3. Acceptable use", "You agree not to use the Service to generate unlawful content, infringe intellectual-property rights, or circumvent the safety controls of any connected model provider. You are responsible for the prompts you submit and the outputs you publish."],
  ["4. Third-party providers", "Generation is routed to third-party providers (including fal.ai, Replicate, and ElevenLabs) and evaluation models. Your use of those services through Genlineage is also subject to their respective terms. We are not liable for provider outages or the content they return."],
  ["5. Provenance and integrity", "Signed manifests are provided for verification convenience. While we take reasonable measures to keep the ledger tamper-evident, you are responsible for independently verifying signatures where authenticity is critical."],
  ["6. Fees", "Paid plans are billed in advance and are non-refundable except where required by law. Provider usage costs incurred through your pipelines may be passed through and are shown in each commit's cost record."],
  ["7. Termination", "You may close your account at any time. We may suspend or terminate access for violations of these Terms. Your committed assets and manifests remain exportable for 30 days after termination."],
  ["8. Disclaimer & liability", "The Service is provided \"as is\" without warranties of any kind. To the maximum extent permitted by law, Genlineage Labs is not liable for indirect, incidental, or consequential damages arising from your use of the Service."],
  ["9. Changes", "We may update these Terms from time to time. Material changes will be announced in-product. Continued use after changes take effect constitutes acceptance."],
];

export default function Terms() {
  return (
    <PageShell eyebrow="Legal" title="TERMS OF SERVICE">
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
