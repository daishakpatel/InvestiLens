import { useState } from "react";

import { CitationChip } from "../citations/CitationChip";
import { Section } from "../ui/Section";
import { AsyncContent } from "../ui/States";
import { formatDate } from "../../lib/format";
import { useManagementLanguage } from "../../lib/queries";
import type { LanguagePoint, LanguageSeries, ManagementLanguageResponse } from "../../types";

interface Selection {
  series: LanguageSeries;
  index: number;
}

const FLAG = { first_appearance: "first appears", disappeared: "drops out" } as const;

function Row({
  series,
  max,
  selected,
  onSelect,
}: {
  series: LanguageSeries;
  max: number;
  selected: Selection | null;
  onSelect: (s: Selection) => void;
}) {
  return (
    <tr className="border-t border-border/60">
      <th scope="row" className="px-4 py-2 text-left font-medium">
        {series.label}
      </th>
      {series.points.map((point: LanguagePoint, index) => {
        const active = selected?.series.topic === series.topic && selected.index === index;
        // Shade encodes intensity; the number is always printed, so colour is never the only cue.
        const shade = max > 0 ? Math.round((point.per_1k_words / max) * 45) : 0;
        return (
          <td key={point.filing_id} className="p-1 text-center">
            <button
              type="button"
              disabled={point.count === 0}
              aria-pressed={active}
              onClick={() => onSelect({ series, index })}
              title={`${point.count} mention${point.count === 1 ? "" : "s"}`}
              style={{
                backgroundColor: `color-mix(in srgb, var(--primary) ${shade}%, transparent)`,
              }}
              className={`w-full rounded-control px-2 py-1.5 tnum ${
                active ? "ring-2 ring-primary" : ""
              } ${point.count === 0 ? "text-muted" : "hover:ring-1 hover:ring-primary"}`}
            >
              {point.per_1k_words.toFixed(1)}
              {point.flag && <span className="block text-[0.65rem]">{FLAG[point.flag]}</span>}
            </button>
          </td>
        );
      })}
    </tr>
  );
}

function Tracker({ data }: { data: ManagementLanguageResponse }) {
  const [selected, setSelected] = useState<Selection | null>(null);
  const max = Math.max(0, ...data.topics.flatMap((t) => t.points.map((p) => p.per_1k_words)));
  const hedgingMax = Math.max(0, ...data.hedging.points.map((p) => p.per_1k_words));
  const point = selected?.series.points[selected.index];
  const period = selected ? data.periods[selected.index] : undefined;

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="px-4 py-2 text-left text-xs text-muted">
            Mentions per 1,000 words of Management’s Discussion &amp; Analysis, by filing. Select a
            cell to read the statements that were counted.
          </caption>
          <thead className="text-xs text-muted">
            <tr>
              <th scope="col" className="px-4 py-2 text-left font-medium">Topic</th>
              {data.periods.map((p) => (
                <th key={p.filing_id} scope="col" className="px-2 py-2 font-medium">
                  {p.filing_type}
                  <span className="block font-normal">ended {formatDate(p.period_end)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.topics.map((series) => (
              <Row key={series.topic} series={series} max={max} selected={selected} onSelect={setSelected} />
            ))}
          </tbody>
          <tbody className="border-t-2 border-border">
            <Row series={data.hedging} max={hedgingMax} selected={selected} onSelect={setSelected} />
          </tbody>
        </table>
      </div>
      <p className="px-4 py-2 text-xs text-muted">
        Hedging language counts words such as “may”, “could”, “expect” and “uncertain”. Both rows
        are word counts from a fixed list ({data.taxonomy_version}, {data.hedging_lexicon_version}),
        not an AI judgment and not a sentiment score.
      </p>
      {selected && point && period && (
        <section aria-label="Counted statements" className="border-t border-border px-4 py-3">
          <h3 className="text-sm font-semibold">
            {selected.series.label} · {period.filing_type} ended {formatDate(period.period_end)} ·{" "}
            {point.count} mention{point.count === 1 ? "" : "s"}
          </h3>
          <ul className="mt-2 max-h-80 space-y-2 overflow-auto text-sm">
            {point.statements.map((s, i) => (
              <li key={i}>
                {s.text} <CitationChip number={i + 1} sourceId={s.source_id} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** Management language tracking (§37.5): topic intensity and hedging index across filings. */
export function LanguageTracker({ ticker }: { ticker: string }) {
  const language = useManagementLanguage(ticker);
  return (
    <Section title="Management language over time">
      <AsyncContent
        query={language}
        isEmpty={(d) => d.periods.length === 0}
        emptyMessage="No parsed annual reports with an MD&A section yet."
      >
        {(data) => <Tracker data={data} />}
      </AsyncContent>
    </Section>
  );
}
