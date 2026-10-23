import { shortPeriod } from "../../charts/series";
import {
  bandLabel,
  bandTone,
  formatQuality,
  latestPoint,
  peerText,
  statusText,
} from "../../lib/earningsQuality";
import type { QualityMeasure } from "../../types";
import { Badge } from "../ui/Badge";

const VARIANTS: Record<string, string> = {
  original: "Original Z (manufacturer)",
  z_double_prime: "Z″ (non-manufacturer)",
};

/** One measure's latest figure, or the reason it has none, in words (DR-EQ-002). */
function Figure({ measure, size }: { measure: QualityMeasure; size: "lead" | "sub" }) {
  const point = latestPoint(measure);
  const reason = statusText(point, measure);
  const band = bandLabel(point?.band);
  const variant = VARIANTS[String(point?.details["model_variant"] ?? "")];
  return (
    <div data-status={point?.status ?? "insufficient_data"}>
      <div className={size === "lead" ? "text-label text-muted" : "text-caption text-muted"}>
        {measure.label}
        {point && <span className="text-subtle"> · {shortPeriod(point.period)}</span>}
      </div>
      {reason === null ? (
        <div
          className={`tnum font-medium text-text ${size === "lead" ? "mt-0.5 text-title" : "text-sm"}`}
        >
          {formatQuality(measure.metric_name, point?.value)}
        </div>
      ) : (
        <p className={`text-sm ${point?.status === "not_applicable" ? "text-subtle" : "text-muted"}`}>
          {point?.status === "not_applicable" ? "N/A. " : ""}
          {reason}
        </p>
      )}
      {(band || variant) && reason === null && (
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
          {band && <Badge tone={bandTone(measure.metric_name, point?.band)}>{band}</Badge>}
          {variant && <span className="text-caption text-subtle">{variant}</span>}
        </div>
      )}
    </div>
  );
}

/** A dashboard card: a lead measure, an optional companion, trailing and peer context, and the
 *  screening caveat under any score (FR-EQ-011/013). No border box: a hairline separates cards. */
export function QualityCard({
  title,
  lead,
  companion,
}: {
  title: string;
  lead: QualityMeasure;
  companion?: QualityMeasure | undefined;
}) {
  const ttm = lead.latest_ttm?.status === "ok" ? lead.latest_ttm : null;
  const peers = peerText(lead);
  const caveat = lead.caveat ?? companion?.caveat;
  return (
    <article
      aria-label={title}
      data-testid={`quality-card-${lead.metric_name}`}
      className="flex min-w-0 flex-col gap-3 border-t border-border pt-4"
    >
      <h3 className="text-sm font-medium text-text">{title}</h3>
      <Figure measure={lead} size="lead" />
      {ttm && (
        <p className="text-caption text-muted">
          TTM {shortPeriod(ttm.period.replace(/^TTM-/, ""))}:{" "}
          <span className="tnum text-text">{formatQuality(lead.metric_name, ttm.value)}</span>
        </p>
      )}
      {companion && <Figure measure={companion} size="sub" />}
      {peers && <p className="text-caption text-subtle">{peers}</p>}
      <p className="text-caption text-subtle">{lead.explanation}</p>
      {caveat && (
        <p role="note" className="mt-auto border-l-2 border-border-strong pl-2 text-caption text-muted">
          {caveat}
        </p>
      )}
    </article>
  );
}
