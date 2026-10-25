import type { ValuationBand } from "../../types";
import { bandGeometry, bandValue } from "../../lib/valuationBands";

/** Today's value on its 5-year range, with the peer median as a tick (FR-PS-014). Every mark is
 *  labelled in text; colour only separates the track from the range. */
export function RangeBar({ band }: { band: ValuationBand }) {
  const g = bandGeometry(band);
  if (!g) return null;
  const today = bandValue(band.value, band.unit);
  const median = band.peers.median ? bandValue(band.peers.median, band.unit) : null;
  const clamp = (pct: number) => Math.min(96, Math.max(4, pct));
  return (
    <div
      role="img"
      aria-label={`Today ${today}; 5-year range ${bandValue(band.own.min, band.unit)} to ${bandValue(band.own.max, band.unit)}${median ? `; peer median ${median}` : ""}`}
      className="relative h-14 select-none"
    >
      <span
        className="tnum absolute top-0 -translate-x-1/2 whitespace-nowrap text-caption font-medium text-text"
        style={{ left: `${clamp(g.today)}%` }}
      >
        Today {today}
      </span>
      <div className="absolute inset-x-0 top-6 h-1.5 rounded-full bg-surface-2" />
      <div
        className="absolute top-6 h-1.5 rounded-full bg-subtle/70"
        style={{ left: `${g.rangeStart}%`, width: `${Math.max(g.rangeEnd - g.rangeStart, 0.5)}%` }}
      />
      <div
        aria-hidden
        className="absolute top-4 h-5 w-0.5 -translate-x-1/2 rounded bg-text"
        style={{ left: `${g.today}%` }}
      />
      {g.peerMedian !== null && median && (
        <>
          <div
            aria-hidden
            className="absolute top-5 h-3.5 w-px -translate-x-1/2 border-l border-dashed border-muted"
            style={{ left: `${g.peerMedian}%` }}
          />
          <span
            className="tnum absolute top-9 -translate-x-1/2 whitespace-nowrap text-caption text-muted"
            style={{ left: `${clamp(g.peerMedian)}%` }}
          >
            Peer median {median}
          </span>
        </>
      )}
    </div>
  );
}
