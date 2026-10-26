/** A price trend in a table row: one line, no axes, coloured by whether the period ended up or
 *  down. Decorative: the figures beside it carry the information, so it is hidden from assistive
 *  tech. Plain SVG, so a list of these does not pull in the chart library. */
export function Sparkline({
  values,
  className = "",
  tone = "trend",
}: {
  values: readonly number[];
  className?: string;
  // "neutral" where up/down is not gain/loss (a thesis KPI: FR-TH-015)
  tone?: "trend" | "neutral";
}) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 100;
  const H = 28;
  const PAD = 2; // room for the 1.5 px stroke at the extremes
  const points = values
    .map((value, i) => {
      const x = (i / (values.length - 1)) * W;
      const y = PAD + (1 - (value - min) / span) * (H - 2 * PAD);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const up = (values.at(-1) ?? 0) >= (values[0] ?? 0);
  return (
    <svg
      aria-hidden
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={`h-7 ${tone === "neutral" ? "text-muted" : up ? "text-positive" : "text-negative"} ${className}`}
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
