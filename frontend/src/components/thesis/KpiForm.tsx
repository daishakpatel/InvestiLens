// Phase 7k (FR-TH-002/005): a KPI is a registry metric, a period, a comparator and a threshold
// typed in the metric's unit (a ratio as a percent, stored as a decimal).
import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import { useMetricRegistry } from "../../lib/thesisQueries";
import { COMPARATOR_SYMBOL, INPUT_SUFFIX, toInput, toThreshold } from "../../lib/thesis";
import type { KpiCreate, MetricRegistryEntry, ThesisKpi } from "../../types";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";

const COMPARATORS = ["gte", "lte", "gt", "lt"] as const;

export function KpiForm({
  ticker,
  initial,
  submitLabel,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  ticker: string;
  initial?: ThesisKpi | KpiCreate | undefined;
  submitLabel: string;
  busy: boolean;
  error: string | null;
  onSubmit: (body: KpiCreate) => void;
  onCancel?: () => void;
}) {
  const registry = useMetricRegistry(ticker);
  const metrics = useMemo(() => registry.data?.metrics ?? [], [registry.data]);
  const [metricKey, setMetricKey] = useState(initial?.metric ?? "gross_margin");
  const metric: MetricRegistryEntry | undefined = metrics.find((m) => m.key === metricKey);
  const [period, setPeriod] = useState<string>(initial?.period_type ?? "TTM");
  const [comparator, setComparator] = useState<KpiCreate["comparator"]>(initial?.comparator ?? "gte");
  const initialUnit = initial && "unit" in initial ? initial.unit : undefined;
  const [value, setValue] = useState(
    initial && initialUnit ? toInput(String(initial.threshold), initialUnit) : initial ? String(initial.threshold) : "",
  );
  const [label, setLabel] = useState(initial?.label ?? "");
  const [rationale, setRationale] = useState(initial?.rationale ?? "");
  const [localError, setLocalError] = useState<string | null>(null);
  const periods = metric?.period_types ?? [];
  const chosenPeriod = periods.includes(period as never) ? period : (periods[0] ?? "");
  const groups = [...new Set(metrics.map((m) => m.group))];

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!metric) return;
    const threshold = toThreshold(value, metric.unit);
    if (threshold === null) {
      setLocalError("Enter the threshold as a number.");
      return;
    }
    setLocalError(null);
    onSubmit({
      metric: metric.key,
      period_type: chosenPeriod as KpiCreate["period_type"],
      comparator,
      threshold,
      label: label.trim(),
      rationale: rationale.trim() || null,
    });
  };

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-surface border border-border bg-surface p-4 md:grid-cols-6" aria-label="KPI">
      <label className="space-y-1 md:col-span-2">
        <span className="text-caption text-muted">Metric</span>
        <Select value={metricKey} onChange={(e) => setMetricKey(e.target.value)} className="w-full" aria-label="Metric">
          {groups.map((group) => (
            <optgroup key={group} label={group}>
              {metrics
                .filter((m) => m.group === group)
                .map((m) => (
                  <option key={m.key} value={m.key} disabled={m.applicable === false}>
                    {m.label}
                    {m.applicable === false ? " (not reported for this sector)" : ""}
                  </option>
                ))}
            </optgroup>
          ))}
        </Select>
      </label>
      <label className="space-y-1">
        <span className="text-caption text-muted">Period</span>
        <Select value={chosenPeriod} onChange={(e) => setPeriod(e.target.value)} className="w-full" aria-label="Period">
          {periods.map((p) => (
            <option key={p} value={p}>
              {p === "LATEST" ? "Latest close" : p}
            </option>
          ))}
        </Select>
      </label>
      <label className="space-y-1">
        <span className="text-caption text-muted">Rule</span>
        <Select
          value={comparator}
          onChange={(e) => setComparator(e.target.value as KpiCreate["comparator"])}
          className="w-full"
          aria-label="Comparator"
        >
          {COMPARATORS.map((c) => (
            <option key={c} value={c}>
              {COMPARATOR_SYMBOL[c]}
            </option>
          ))}
        </Select>
      </label>
      <label className="space-y-1 md:col-span-2">
        <span className="text-caption text-muted">Threshold ({metric ? INPUT_SUFFIX[metric.unit] : ""})</span>
        <Input
          inputMode="decimal"
          required
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-label="Threshold"
          placeholder={metric?.unit === "ratio" ? "e.g. 70 for 70%" : "e.g. 25"}
        />
      </label>
      <label className="space-y-1 md:col-span-3">
        <span className="text-caption text-muted">Label (your words)</span>
        <Input required maxLength={120} value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Label" />
      </label>
      <label className="space-y-1 md:col-span-3">
        <span className="text-caption text-muted">Why it matters (optional)</span>
        <Input maxLength={1000} value={rationale} onChange={(e) => setRationale(e.target.value)} aria-label="Rationale" />
      </label>
      {metric && <p className="text-caption text-subtle md:col-span-6">{metric.description}</p>}
      {(localError ?? error) && (
        <p role="alert" className="text-sm text-negative md:col-span-6">
          {localError ?? error}
        </p>
      )}
      <div className="flex gap-2 md:col-span-6">
        <Button type="submit" variant="primary" size="sm" loading={busy} disabled={!metric}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
