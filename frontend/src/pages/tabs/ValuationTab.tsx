import { useParams } from "react-router-dom";

import { AsyncContent, Panel } from "../../components/Panel";
import { Badge } from "../../components/primitives";
import { formatMetricValue } from "../../lib/format";
import { useValuation } from "../../lib/queries";

export default function ValuationTab() {
  const { ticker = "" } = useParams();
  const valuation = useValuation(ticker);

  return (
    <Panel title="Valuation metrics" freshness={valuation.data?.freshness}>
      <AsyncContent
        query={valuation}
        isEmpty={(d) => d.metrics.length === 0}
        emptyMessage="No valuation metrics yet — these depend on price-derived values (persisted in a later ingestion pass)."
      >
        {(data) => (
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-2 text-xs uppercase text-muted">
              <tr>
                <th scope="col" className="px-4 py-2">
                  Metric
                </th>
                <th scope="col" className="px-4 py-2 text-right">
                  Value
                </th>
                <th scope="col" className="px-4 py-2">
                  Notes
                </th>
              </tr>
            </thead>
            <tbody>
              {data.metrics.map((m) => (
                <tr key={m.formula_id} className="border-t border-border">
                  <td className="px-4 py-2 font-medium">{m.formula_id}</td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {formatMetricValue(m.value, m.unit)}
                  </td>
                  <td className="px-4 py-2">
                    {m.warnings.length > 0 && <Badge tone="warning">{m.warnings.join(", ")}</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </AsyncContent>
    </Panel>
  );
}
