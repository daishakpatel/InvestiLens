// Last close and day-over-day change from a daily price series. One implementation shared by the
// company header, the sticky sub-header, and the home ticker rows, so they can never disagree.
import { toNumber } from "./format";

export interface Quote {
  close: number;
  changePct: number | null; // ratio vs the prior session; null when there is no prior close
  date: string;
}

export function latestQuote(
  points: readonly { date: string; close?: string | null }[] | undefined,
): Quote | null {
  const last = points?.at(-1);
  const close = toNumber(last?.close ?? null);
  if (!last || close === null) return null;
  const prev = toNumber(points?.at(-2)?.close ?? null);
  return { close, changePct: prev ? (close - prev) / prev : null, date: last.date };
}
