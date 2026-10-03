import { Panel } from "../../components/Panel";

/** A tab whose content is built in a later phase; the shell exists now (dashboard scope). */
export function PlaceholderTab({ title, note }: { title: string; note: string }) {
  return (
    <Panel title={title} kind={title.toLowerCase().includes("chat") ? "ai" : "data"}>
      <div className="p-6 text-sm text-muted">{note}</div>
    </Panel>
  );
}

export function ResearchTab() {
  return (
    <PlaceholderTab
      title="AI Research"
      note="Full generated report with citations and evidence-strength badges arrives in Phase 4d."
    />
  );
}
export function RisksTab() {
  return <PlaceholderTab title="Risks" note="AI-interpreted risk factors arrive in Phase 4d." />;
}
export function ManagementTab() {
  return (
    <PlaceholderTab title="Management" note="Management commentary analysis arrives in Phase 4d." />
  );
}
export function OwnershipTab() {
  return (
    <PlaceholderTab
      title="Insiders & Ownership"
      note="Form 4 insider transactions and 13F holdings are a P2 ingestion feature; not yet available."
    />
  );
}
export function ChatTab() {
  return (
    <PlaceholderTab
      title="Chat"
      note="Streaming Q&A over the company's research corpus, with citations, arrives in Phase 4d."
    />
  );
}
