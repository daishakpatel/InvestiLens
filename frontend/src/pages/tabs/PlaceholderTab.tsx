import { Panel } from "../../components/Panel";

/** Insiders & Ownership: Form 4 / 13F ingestion is a P2 feature; show a clear "coming soon". */
export function OwnershipTab() {
  return (
    <Panel title="Insiders & Ownership">
      <p className="p-6 text-sm text-muted">
        Insider transactions (Form 4) and institutional holdings (13F) aren’t ingested yet (a P2
        data source). This tab will populate once that data lands.
      </p>
    </Panel>
  );
}
