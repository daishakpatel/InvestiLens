import { formatDate } from "../../lib/format";
import { useManagementLanguage } from "../../lib/queries";
import type { LanguagePoint, LanguageSeries, ManagementLanguageResponse } from "../../types";
import { useCitations } from "../citations/CitationContext";
import { AsyncContent } from "../ui/States";

type Period = ManagementLanguageResponse["periods"][number];

const FLAG = { first_appearance: "first appears here", disappeared: "drops out here" } as const;

function periodName(period: Period): string {
  return `${period.filing_type} for the period ended ${formatDate(period.period_end)}`;
}

function Row({
  series,
  periods,
  max,
  unit,
}: {
  series: LanguageSeries;
  periods: Period[];
  max: number;
  unit: string; // what is being counted, for the panel: "mentions" or "hedging words"
}) {
  const { openStatements } = useCitations();
  return (
    <tr>
      <th scope="row" className="whitespace-nowrap py-px pr-4 text-left text-sm font-normal text-text">
        {series.label}
      </th>
      {series.points.map((point: LanguagePoint, index) => {
        const period = periods[index];
        if (!period) return null;
        // Shade carries intensity; the figure is always printed, so colour is never the only cue.
        const shade = max > 0 ? Math.round((point.per_1k_words / max) * 55) : 0;
        const flag = point.flag ? FLAG[point.flag] : null;
        const describe = `${series.label}, ${periodName(period)}: ${point.per_1k_words.toFixed(1)} per 1,000 words, ${point.count} ${point.count === 1 ? "mention" : "mentions"}${flag ? `, ${flag}` : ""}`;
        return (
          <td key={point.filing_id} className="p-px">
            <button
              type="button"
              disabled={point.count === 0}
              aria-label={point.count > 0 ? `${describe}. Show the statements counted.` : describe}
              title={flag ? `${series.label} ${flag}` : undefined}
              onClick={() =>
                openStatements({
                  kind: "statements",
                  title: series.label,
                  subtitle: `${point.count} ${unit} in the ${periodName(period)} (${point.per_1k_words.toFixed(1)} per 1,000 words of Management’s Discussion & Analysis)`,
                  statements: point.statements,
                })
              }
              style={{ backgroundColor: `color-mix(in srgb, var(--primary) ${shade}%, var(--surface))` }}
              className={`tnum relative block h-9 w-full min-w-14 text-sm transition-shadow pointer-coarse:h-10 ${
                point.count === 0
                  ? "cursor-default text-subtle"
                  : "text-text hover:shadow-[inset_0_0_0_1px_var(--primary)]"
              }`}
            >
              {point.per_1k_words.toFixed(1)}
              {point.flag && (
                <span
                  aria-hidden
                  className={`absolute right-1.5 top-1.5 size-1.5 rounded-full ${
                    point.flag === "first_appearance" ? "bg-text" : "border border-text"
                  }`}
                />
              )}
            </button>
          </td>
        );
      })}
    </tr>
  );
}

function Grid({ data }: { data: ManagementLanguageResponse }) {
  const max = Math.max(0, ...data.topics.flatMap((t) => t.points.map((p) => p.per_1k_words)));
  const hedgingMax = Math.max(0, ...data.hedging.points.map((p) => p.per_1k_words));
  const flagged = data.topics.some((topic) => topic.points.some((point) => point.flag));

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0">
          <caption className="pb-3 text-left text-caption text-muted">
            Mentions per 1,000 words of Management’s Discussion &amp; Analysis, by filing. Select a
            figure to read the statements that were counted.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="pb-2 pr-4 text-left text-label font-medium text-muted">
                Topic
              </th>
              {data.periods.map((period) => (
                <th
                  key={period.filing_id}
                  scope="col"
                  className="px-1 pb-2 text-center text-label font-medium text-muted"
                >
                  {period.filing_type}
                  <span className="block whitespace-nowrap font-normal text-subtle">
                    {formatDate(period.period_end)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.topics.map((series) => (
              <Row key={series.topic} series={series} periods={data.periods} max={max} unit="mentions" />
            ))}
          </tbody>
          {/* Hedging is a different measure on its own scale, so it sits apart from the topics. */}
          <tbody>
            <tr aria-hidden>
              <td colSpan={data.periods.length + 1} className="h-3" />
            </tr>
            <Row series={data.hedging} periods={data.periods} max={hedgingMax} unit="hedging words" />
          </tbody>
        </table>
      </div>
      <p className="mt-3 max-w-2xl text-caption text-subtle">
        Hedging language counts words such as “may”, “could”, “expect” and “uncertain”. Every figure
        here is a count against a fixed word list ({data.taxonomy_version},{" "}
        {data.hedging_lexicon_version}): a measure of wording, not an AI judgment and not a
        sentiment score.
        {flagged && " A filled dot marks where a topic first appears; a hollow one, where it drops out."}
      </p>
    </div>
  );
}

/** Management language tracking (§37.5): how often each topic comes up in MD&A, filing by filing,
 *  as a heat table. Deterministic counts, each traceable to the sentences counted. */
export function LanguageTracker({ ticker }: { ticker: string }) {
  const language = useManagementLanguage(ticker);
  return (
    <AsyncContent
      query={language}
      isEmpty={(data) => data.periods.length === 0}
      emptyMessage="No parsed annual reports with a Management’s Discussion & Analysis section yet."
    >
      {(data) => <Grid data={data} />}
    </AsyncContent>
  );
}
