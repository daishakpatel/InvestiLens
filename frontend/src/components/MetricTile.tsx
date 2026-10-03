import { Tooltip } from "./primitives";

export interface MetricMeta {
  source?: string | undefined;
  period?: string | undefined;
  formula?: string | undefined;
  lastUpdated?: string | undefined;
}

/** A company-header metric with a tooltip exposing source/period/formula/last_updated (§9.4). */
export function MetricTile({
  label,
  value,
  meta,
}: {
  label: string;
  value: string;
  meta?: MetricMeta;
}) {
  const rows = meta
    ? [
        ["Source", meta.source],
        ["Period", meta.period],
        ["Formula", meta.formula],
        ["Last updated", meta.lastUpdated],
      ].filter((r): r is [string, string] => Boolean(r[1]))
    : [];

  const valueEl = <span className="text-lg font-semibold tabular-nums">{value}</span>;

  return (
    <div className="min-w-24">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      {rows.length ? (
        <Tooltip
          label={
            <dl className="space-y-1">
              {rows.map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <dt className="text-muted">{k}:</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          }
        >
          {valueEl}
        </Tooltip>
      ) : (
        valueEl
      )}
    </div>
  );
}
