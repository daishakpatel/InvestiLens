# ADR-0034: Every stored metric gets its own source ID

- **Status:** Accepted
- **Date:** 2026-10-13
- **Spec refs:** §13.2, §13.3, §13.4, CIT-001, CIT-002, CIT-003, FR-027, DR-022, DR-023

## Problem

A base metric taken from a filing stored that filing's accession number as its `source_id`. One
10-K reports revenue, net income, operating income and dozens more, so they all shared one ID
(3,209 latest rows, 1,393 distinct IDs in the dev database). `GET /sources/{id}` and the chat's
metric path look a metric up by that ID and got whichever row came first: a question about net
income was answered, and cited, with revenue, and every lineage chip on a derived metric opened
the same wrong figure. Derived Q4 values used `q4_derived:<metric>`, which also collided across
companies and years.

## Decision

`app/finance/builder.py` now issues `xbrl:<TICKER>:<metric>:FY<year>` for a base annual metric and
`derived:<TICKER>:<metric>:Q4-FY<year>` for a derived fourth quarter, matching the ratio scheme
from ADR-0026 (`derived:<TICKER>:<formula_id>:FY<year>`). The filing is still recorded in
`as_reported_accession` and still supplies the citation's accession number and SEC link.
Restated versions of one metric and period share the ID; only the `is_latest` row resolves. A
derived Q4's lineage is now written in the same shape as ratio lineage (the annual figure by its
source ID, the three quarters by filing); it was a list of bare accession strings, which made
`GET /sources` fail with a 500 for any derived quarter. No
schema change: existing databases pick the new IDs up by re-running
`scripts/build_metrics.py`, which clears and rebuilds each company's metrics and ratio lineage.

## Consequences

A source ID now names exactly one figure, so chat answers, the citation panel and lineage chips
agree with the question asked; `test_every_latest_metric_has_its_own_source_id` holds the
invariant. A citation stored before the rebuild that used a bare accession number as a metric ID
no longer resolves (none existed in the dev database). The raw-fact form `xbrl:<fact id>` is
unchanged and is told apart by its integer suffix.
