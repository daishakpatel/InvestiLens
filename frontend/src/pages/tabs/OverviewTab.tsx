import { useParams } from "react-router-dom";

import { DataRefreshChecklist } from "../../components/DataRefreshChecklist";
import { AsyncContent, Panel } from "../../components/Panel";
import { useCompany, useDataFreshness } from "../../lib/queries";

export default function OverviewTab() {
  const { ticker = "" } = useParams();
  const company = useCompany(ticker);
  const freshness = useDataFreshness(ticker);

  return (
    <div className="space-y-4">
      <Panel title="Company overview" freshness={company.data?.freshness}>
        <AsyncContent query={company}>
          {(data) => {
            const c = data.company;
            const rows = [
              ["Exchange", c.exchange],
              ["Sector", c.sector],
              ["Industry", c.industry],
              ["Fiscal year end", c.fiscal_year_end],
              ["CIK", c.cik],
            ].filter((r): r is [string, string] => Boolean(r[1]));
            return (
              <dl className="grid grid-cols-1 gap-x-8 gap-y-2 p-4 text-sm sm:grid-cols-2">
                {rows.map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-4 border-b border-border/60 py-1">
                    <dt className="text-muted">{k}</dt>
                    <dd className="font-medium">{v}</dd>
                  </div>
                ))}
              </dl>
            );
          }}
        </AsyncContent>
      </Panel>

      <AsyncContent query={freshness}>
        {(data) => <DataRefreshChecklist sources={data.sources} />}
      </AsyncContent>
    </div>
  );
}
