import { useState } from "react";

import { ApiError } from "../../lib/apiClient";
import { MAX_COMPANIES } from "../../lib/compare";
import { useAuth } from "../../lib/auth";
import { useDeletePeerSet, usePeerSets, useSavePeerSet, useValuationBands } from "../../lib/queries";
import type { PeerSetOut } from "../../types";
import { SignInHint } from "../SignInHint";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

/** Edit a peer set the user owns, or start one from the default (FR-PS-003). The server's
 *  message is shown as is: it names any ticker Assay Desk does not have yet. */
function Editor({ ticker, from, onDone }: { ticker: string; from: PeerSetOut; onDone: (id: number | null) => void }) {
  const own = from.kind === "user";
  const [name, setName] = useState(own ? from.name : `My peers for ${ticker}`);
  const [tickers, setTickers] = useState(from.members.map((m) => m.ticker).join(", "));
  const save = useSavePeerSet(ticker);
  const remove = useDeletePeerSet(ticker);
  const error = save.error instanceof ApiError ? save.error.message : save.error ? "The peer set could not be saved." : null;
  return (
    <form
      className="mt-3 space-y-3 rounded-control border border-border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        const list = tickers.split(/[\s,]+/).filter(Boolean);
        save.mutate(
          { ...(own ? { id: from.id } : {}), name, tickers: list },
          { onSuccess: (saved) => onDone(saved.id) },
        );
      }}
    >
      <label className="block text-caption text-muted">
        Name
        <Input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} className="mt-1" />
      </label>
      <label className="block text-caption text-muted">
        Tickers (up to 12, separated by commas)
        <Input value={tickers} onChange={(e) => setTickers(e.target.value)} className="mt-1" />
      </label>
      {error && (
        <p role="alert" className="text-caption text-negative">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={save.isPending}>
          Save peer set
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => onDone(null)}>
          Cancel
        </Button>
        {own && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => remove.mutate(from.id, { onSuccess: () => onDone(null) })}
          >
            Delete
          </Button>
        )}
      </div>
    </form>
  );
}

/** The peer sets of the first company on the Compare view: the rule-based default with each
 *  member's reason ("why these peers?"), the user's own sets, and an editor (FR-PS-013). Peers
 *  the valuation bands had to leave out are greyed with the reason. */
export function PeerSetPanel({ ticker, onCompare }: { ticker: string; onCompare: (tickers: string[]) => void }) {
  const { user } = useAuth();
  const sets = usePeerSets(ticker, user !== null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const all = sets.data?.peer_sets ?? [];
  const selected = all.find((s) => s.id === selectedId) ?? all[0];
  const bands = useValuationBands(ticker, selected?.id ?? null);
  if (!selected) return null;
  const excluded = new Map(
    (bands.data?.bands.find((b) => b.multiple === "pe_ratio")?.peers.excluded ?? []).map((e) => [e.ticker, e.reason]),
  );
  return (
    <section aria-label={`Peer sets for ${ticker}`} className="space-y-2" data-testid="peer-sets">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-caption text-subtle">Peer sets for {ticker}</span>
        {all.map((set) => (
          <button
            key={set.id}
            type="button"
            aria-pressed={set.id === selected.id}
            onClick={() => {
              setSelectedId(set.id);
              setEditing(false);
            }}
            className={`inline-flex h-7 items-center rounded-full border px-3 text-label ${
              set.id === selected.id ? "border-border-strong bg-surface-2 text-text" : "border-border text-muted hover:text-text"
            }`}
          >
            {set.name}
            <span className="ml-1.5 tnum text-subtle">{set.members.length}</span>
          </button>
        ))}
        {selected.members.length > 0 && (
          <Button size="sm" variant="ghost" onClick={() => onCompare([ticker, ...selected.members.map((m) => m.ticker)])}>
            Compare with these
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => setEditing((v) => !v)} aria-expanded={editing}>
          Edit
        </Button>
      </div>
      {selected.members.length + 1 > MAX_COMPANIES && (
        <p className="text-caption text-subtle">
          Compare shows {MAX_COMPANIES} companies at a time: the first {MAX_COMPANIES - 1} of these{" "}
          {selected.members.length} peers are added.
        </p>
      )}
      {selected.insufficient && (
        <p role="note" className="text-caption text-warning">
          {selected.reason ?? "Insufficient peers: fewer than three companies, so peer figures are hidden."}
        </p>
      )}
      <details>
        <summary className="cursor-pointer text-caption text-muted">Why these peers?</summary>
        {selected.members.length === 0 ? (
          <p className="mt-2 text-caption text-subtle">No company in Assay Desk meets the rule for this set.</p>
        ) : (
          <ul className="mt-2 space-y-1 text-caption">
            {selected.members.map((m) => {
              const left = excluded.get(m.ticker);
              return (
                <li key={m.ticker} className={left ? "text-subtle opacity-70" : "text-muted"} title={left}>
                  <span className="font-medium text-text">{m.ticker}</span> {m.name} · {m.rationale}
                  {left && <span> · left out of the P/E band: {left}</span>}
                </li>
              );
            })}
          </ul>
        )}
      </details>
      {editing &&
        (user ? (
          <Editor
            key={selected.id}
            ticker={ticker}
            from={selected}
            onDone={(id) => {
              setEditing(false);
              if (id !== null) setSelectedId(id);
            }}
          />
        ) : (
          <SignInHint>Sign in to make a peer set of your own.</SignInHint>
        ))}
    </section>
  );
}
