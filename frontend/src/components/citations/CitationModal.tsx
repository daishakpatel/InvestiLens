import { useEffect, useRef, useState } from "react";

import { useSource } from "../../lib/queries";
import type { SourceDetail, SourceRecord } from "../../types";
import { Badge, ErrorState, LoadingState } from "../primitives";
import { sourceKindLabel, sourceTitle } from "./sourceTitle";

function HighlightedText({
  text,
  start,
  end,
}: {
  text: string;
  start: number | null | undefined;
  end: number | null | undefined;
}) {
  if (start === null || start === undefined || end === null || end === undefined || end <= start) {
    return <p className="whitespace-pre-wrap text-sm leading-relaxed">{text}</p>;
  }
  const s = Math.max(0, start);
  const e = Math.min(text.length, end);
  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed">
      {text.slice(0, s)}
      <mark className="rounded bg-warning/30 px-0.5 text-text">{text.slice(s, e)}</mark>
      {text.slice(e)}
    </p>
  );
}

function Derivation({
  source,
  lineage,
  onOpenSource,
}: {
  source: Extract<SourceRecord, { source_type: "derived_metric" }>;
  lineage: Record<string, string>[];
  onOpenSource: (id: string) => void;
}) {
  return (
    <div className="mt-3 rounded-lg border border-border bg-surface-2 p-3 text-sm">
      <div className="mb-2 font-medium">How this was calculated</div>
      <dl className="space-y-1">
        <Row k="Formula" v={`${source.formula_id} (v${source.formula_version})`} />
        {source.value != null && <Row k="Value" v={source.value} />}
        {source.period && <Row k="Period" v={source.period} />}
      </dl>
      {lineage.length > 0 && (
        <table className="mt-2 w-full text-left text-xs">
          <tbody>
            {lineage.map((row, i) => (
              <tr key={i} className="border-t border-border">
                {Object.entries(row).map(([k, v]) => (
                  <td key={k} className="px-1 py-0.5">
                    <span className="text-muted">{k}:</span> {v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {source.input_source_ids.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
          <span className="text-muted">Inputs:</span>
          {source.input_source_ids.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => onOpenSource(id)}
              className="rounded bg-primary/10 px-1.5 py-0.5 font-medium text-primary hover:bg-primary/20"
            >
              {id}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-muted">{k}</dt>
      <dd className="font-medium">{v}</dd>
    </div>
  );
}

function Body({
  detail,
  onOpenSource,
}: {
  detail: SourceDetail;
  onOpenSource: (id: string) => void;
}) {
  const [showDerivation, setShowDerivation] = useState(false);
  const source = detail.source;
  const sectionPath =
    source.source_type === "text_chunk" && source.section_path.length
      ? source.section_path.join(" › ")
      : null;
  const page = source.source_type === "text_chunk" ? source.page : null;

  const copyCitation = () => {
    const ref = detail.deep_link ?? source.source_id;
    void navigator.clipboard?.writeText(`${sourceTitle(source)} — ${ref}`);
  };

  return (
    <div className="p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{sourceKindLabel(source)}</Badge>
        <Badge tone="neutral">Tier {source.tier}</Badge>
        {sectionPath && <span className="text-xs text-muted">{sectionPath}</span>}
        {page != null && <span className="text-xs text-muted">p. {page}</span>}
      </div>

      {detail.text ? (
        <HighlightedText text={detail.text} start={detail.highlight_start} end={detail.highlight_end} />
      ) : (
        <p className="text-sm text-muted">No excerpt available for this source.</p>
      )}

      {source.source_type === "derived_metric" && showDerivation && (
        <Derivation source={source} lineage={detail.lineage} onOpenSource={onOpenSource} />
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {detail.deep_link && (
          <a
            href={detail.deep_link}
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-md border border-border px-3 py-1 text-sm hover:bg-surface-2"
          >
            Open original ↗
          </a>
        )}
        <button
          type="button"
          onClick={copyCitation}
          className="rounded-md border border-border px-3 py-1 text-sm hover:bg-surface-2"
        >
          Copy citation
        </button>
        {source.source_type === "derived_metric" && (
          <button
            type="button"
            onClick={() => setShowDerivation((v) => !v)}
            className="rounded-md border border-border px-3 py-1 text-sm hover:bg-surface-2"
          >
            {showDerivation ? "Hide derivation" : "View derivation"}
          </button>
        )}
      </div>
    </div>
  );
}

export function CitationModal({
  sourceId,
  onClose,
  onOpenSource,
}: {
  sourceId: string | null;
  onClose: () => void;
  onOpenSource: (id: string) => void;
}) {
  const query = useSource(sourceId);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (sourceId === null) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sourceId, onClose]);

  if (sourceId === null) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:p-10"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Source detail"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl rounded-xl border border-border bg-surface shadow-2xl"
      >
        <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">
            {query.data ? sourceTitle(query.data.source) : "Source"}
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md border border-border px-2 py-1 text-sm hover:bg-surface-2"
          >
            ✕
          </button>
        </header>
        {query.isPending ? (
          <LoadingState label="Loading source…" />
        ) : query.isError ? (
          <ErrorState
            message={query.error instanceof Error ? query.error.message : "Could not load source."}
            onRetry={() => void query.refetch()}
          />
        ) : (
          <Body detail={query.data} onOpenSource={onOpenSource} />
        )}
      </div>
    </div>
  );
}
