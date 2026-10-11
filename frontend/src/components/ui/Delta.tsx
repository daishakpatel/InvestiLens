import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { formatPercent, toNumber } from "../../lib/format";

/** A signed change. Direction is carried by sign, arrow, and colour, never colour alone (UI-003). */
export function Delta({
  value,
  digits = 2,
  points = false,
  className = "",
}: {
  value: number | string | null | undefined; // ratio: 0.0123 = +1.23%
  digits?: number;
  points?: boolean; // the value is a change in a ratio (a margin): print "+1.2 pts", not "%"
  className?: string;
}) {
  const ratio = typeof value === "number" ? value : toNumber(value ?? null);
  if (ratio === null || Number.isNaN(ratio)) return null;
  const flat = ratio === 0;
  const up = ratio > 0;
  const Arrow = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={`tnum inline-flex items-center gap-0.5 font-medium ${
        flat ? "text-muted" : up ? "text-positive" : "text-negative"
      } ${className}`}
    >
      {!flat && <Arrow aria-hidden className="size-[1em]" />}
      {up ? "+" : flat ? "" : "−"}
      {points ? `${(Math.abs(ratio) * 100).toFixed(digits)} pts` : formatPercent(Math.abs(ratio), digits)}
    </span>
  );
}
