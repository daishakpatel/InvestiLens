/** The one tooltip for every chart. The value leads; what it is and where it comes from follow. */
export function ChartTooltip({
  value,
  title,
  lines = [],
}: {
  value: string;
  title: string;
  lines?: (string | null | false | undefined)[];
}) {
  return (
    <div className="rounded-control border border-border-strong bg-surface px-3 py-2 text-caption shadow-float">
      <div className="tnum text-sm font-medium text-text">{value}</div>
      <div className="text-muted">{title}</div>
      {lines.filter(Boolean).map((line) => (
        <div key={String(line)} className="text-subtle">
          {line}
        </div>
      ))}
    </div>
  );
}
