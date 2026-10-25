import { useState } from "react";

import { useAuth } from "../../lib/auth";
import { formatDate } from "../../lib/format";
import { useValuationBands, usePeerSets } from "../../lib/queries";
import { bandSummary, bandValue, multipleLabel } from "../../lib/valuationBands";
import type { ValuationBand } from "../../types";
import { Select } from "../ui/Select";
import { ErrorState, LoadingState } from "../ui/States";
import { RangeBar } from "./RangeBar";

function BandRow({ band }: { band: ValuationBand }) {
  const drawn = band.status === "ok" && band.own.min != null && band.value != null;
  const instead = drawn ? null : (band.reason ?? band.own.reason ?? "No band for this multiple.");
  const range =
    drawn && band.own.min != null
      ? `5-year range ${bandValue(band.own.min, band.unit)}–${bandValue(band.own.max, band.unit)}, median ${bandValue(band.own.median, band.unit)}`
      : "";
  return (
    <li className="grid gap-x-8 gap-y-2 py-4 sm:grid-cols-[10rem_minmax(0,1fr)]" data-testid={`band-${band.multiple}`}>
      <div>
        <p className="text-sm font-medium text-text">{multipleLabel(band.multiple)}</p>
        <p className="tnum text-sm text-muted">{band.value != null ? bandValue(band.value, band.unit) : "—"}</p>
      </div>
      <div className="min-w-0">
        {drawn ? (
          <RangeBar band={band} />
        ) : (
          <p role="status" className="text-sm text-muted">
            {instead}
          </p>
        )}
        <p className="mt-1 text-caption text-subtle">
          {[range, bandSummary(band, instead)].filter(Boolean).join("; ")}
        </p>
        {band.peers.excluded.length > 0 && (
          <ul aria-label="Peers left out" className="mt-1 flex flex-wrap gap-x-4 text-caption text-subtle">
            {band.peers.excluded.map((peer) => (
              <li key={peer.ticker} title={peer.reason} className="opacity-70">
                <span className="line-through decoration-subtle">{peer.ticker}</span> {peer.reason}
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

/** Each multiple against its own five fiscal year ends and against a peer set (FR-PS-009..018).
 *  Positions only: where today sits, never whether that is high or low value. */
export function ValuationBands({ ticker }: { ticker: string }) {
  const { user } = useAuth();
  const sets = usePeerSets(ticker, user !== null);
  const [peerSetId, setPeerSetId] = useState<number | null>(null);
  const bands = useValuationBands(ticker, peerSetId);
  const chosen = bands.data?.peer_set;
  return (
    <div className="pt-8" data-testid="valuation-bands">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-text">Valuation bands</h3>
          <p className="text-caption text-subtle">
            Trailing-twelve-month multiples on {formatDate(bands.data?.as_of)}, against this company's last five
            fiscal year ends and its peers. Year-end values use only what had been filed by then.
          </p>
        </div>
        {(sets.data?.peer_sets.length ?? 0) > 0 && (
          <Select
            aria-label="Peer set"
            value={String(peerSetId ?? chosen?.id ?? "")}
            onChange={(e) => setPeerSetId(Number(e.target.value))}
          >
            {sets.data?.peer_sets.map((set) => (
              <option key={set.id} value={set.id}>
                {set.name} ({set.members.length})
              </option>
            ))}
          </Select>
        )}
      </div>
      {chosen?.insufficient && (
        <p role="note" className="mt-3 max-w-3xl text-caption text-warning">
          {chosen.reason ?? "Insufficient peers: this set has fewer than three companies, so peer figures are hidden."}
        </p>
      )}
      {bands.isPending ? (
        <LoadingState label="Loading valuation bands" />
      ) : bands.isError ? (
        <ErrorState message="Valuation bands could not be loaded." onRetry={() => void bands.refetch()} />
      ) : (
        <>
          <ul className="mt-2 divide-y divide-border/60">
            {bands.data.bands.map((band) => (
              <BandRow key={band.multiple} band={band} />
            ))}
          </ul>
          <p className="mt-2 text-caption text-subtle">{bands.data.disclaimer}</p>
        </>
      )}
    </div>
  );
}
