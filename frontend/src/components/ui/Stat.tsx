import type { ReactNode } from "react";

import { Tooltip } from "./Tooltip";

export interface StatMeta {
  source?: string | undefined;
  period?: string | undefined;
  formula?: string | undefined;
  lastUpdated?: string | undefined;
}

/** A labelled figure. `meta` exposes source / period / formula / last updated on hover or focus
 *  (§9.4); `delta` is usually a `<Delta>`. */
export function Stat({
  label,
  value,
  delta,
  meta,
}: {
  label: string;
  value: string;
  delta?: ReactNode;
  meta?: StatMeta;
}) {
  const rows = meta
    ? [
        ["Source", meta.source],
        ["Period", meta.period],
        ["Formula", meta.formula],
        ["Last updated", meta.lastUpdated],
      ].filter((r): r is [string, string] => Boolean(r[1]))
    : [];

  const figure = <span className="tnum text-title font-medium text-text">{value}</span>;

  return (
    <div className="min-w-24">
      <div className="text-label text-muted">{label}</div>
      <div className="mt-0.5 flex items-baseline gap-2">
        {rows.length ? (
          <Tooltip
            plain
            label={
              <dl className="space-y-1">
                {rows.map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <dt className="text-muted">{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            }
          >
            {figure}
          </Tooltip>
        ) : (
          figure
        )}
        {delta && <span className="text-label">{delta}</span>}
      </div>
    </div>
  );
}
