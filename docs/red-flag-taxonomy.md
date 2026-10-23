# Red-flag taxonomy reference (`red_flag_taxonomy_v1`)

Phase 7e, ADR-0043. Generated from `backend/app/redflags/taxonomy.py`; a test checks every rule
key appears here. A flag means **an event is reported in a filing**, never that the company is in
trouble. Severity says how closely an analyst would usually read it (`critical` = read closely,
`warning` = worth reading, `info` = for awareness), not whether it is bad. No AI classifies
anything: every trigger is an 8-K item code, a form type, a phrase rule or a stored figure.

Sources checked on 2026-10-22: SEC Form 8-K General Instructions, "SEC 873 (02-25)"
(https://www.sec.gov/files/form8-k.pdf) for every item number and title; SEC Form 12b-25,
"Notification of Late Filing" (Rule 12b-25, https://www.sec.gov/files/form12b-25.pdf).

| Key | Label | Severity | Trigger source | What it means |
|-----|-------|----------|----------------|---------------|
| `non_reliance` | Non-reliance on previously issued financial statements | critical | SEC Form 8-K (SEC 873, 02-25), Item 4.02 | Item 4.02: the company says earlier financial statements should no longer be relied on, usually because of an error. They are typically restated later. |
| `auditor_change` | Change of auditor reported | warning | SEC Form 8-K (SEC 873, 02-25), Item 4.01 | Item 4.01: the independent accountant resigned, declined to stand for re-appointment or was dismissed. The filing must say whether there were disagreements. |
| `late_filing_notice` | Late-filing notice | warning | SEC Form 12b-25 (Rule 12b-25), filed as NT 10-K / NT 10-Q | Form 12b-25: the company told the SEC a 10-K or 10-Q will not be filed on time and why. A short extension follows automatically. |
| `exec_departure` | Officer or director departure reported | info | SEC Form 8-K (SEC 873, 02-25), Item 5.02(b) | Item 5.02: a principal officer or director is leaving. Many departures are planned retirements or transitions. |
| `exec_change_unspecified` | Leadership change reported | info | SEC Form 8-K (SEC 873, 02-25), Item 5.02 | Item 5.02 describes a departure without naming one of the principal roles we track. Read the item for who is affected. |
| `impairment` | Material impairment reported | warning | SEC Form 8-K (SEC 873, 02-25), Item 2.06 | Item 2.06: the company concluded an asset's value is materially impaired and will record a charge. |
| `restructuring` | Exit or restructuring costs reported | info | SEC Form 8-K (SEC 873, 02-25), Item 2.05 | Item 2.05: the company committed to an exit or disposal plan, such as a restructuring, with material costs. |
| `delisting_notice` | Delisting or listing-standard notice reported | critical | SEC Form 8-K (SEC 873, 02-25), Item 3.01 | Item 3.01: an exchange notified the company of delisting or of a failure to meet a listing standard, or the company is transferring its listing. |
| `bankruptcy` | Bankruptcy or receivership reported | critical | SEC Form 8-K (SEC 873, 02-25), Item 1.03 | Item 1.03: a receiver or similar officer was appointed for the company or a significant subsidiary, for example in a Chapter 11 case. |
| `material_cyber_incident` | Material cybersecurity incident reported | warning | SEC Form 8-K (SEC 873, 02-25), Item 1.05 | Item 1.05: the company determined a cybersecurity incident is material and describes its nature, scope and likely impact. |
| `change_in_control` | Change in control reported | info | SEC Form 8-K (SEC 873, 02-25), Item 5.01 | Item 5.01: control of the company changed, for example after an acquisition of its shares. |
| `going_concern` | Going-concern doubt reported | critical | ASC 205-40 wording in a 10-K / 10-Q | The filing states substantial doubt about the company's ability to continue as a going concern for the next year. |
| `going_concern_alleviated` | Going-concern doubt alleviated by management's plans | warning | ASC 205-40 wording in a 10-K / 10-Q | The filing describes conditions that raised substantial doubt and says management's plans alleviate it. |
| `going_concern_risk_language` | Going-concern risk language | info | ASC 205-40 wording in a 10-K / 10-Q (conditional) | A conditional statement, often a risk factor: substantial doubt could arise if something happens. It is not a conclusion that doubt exists. |
| `material_weakness` | Material weakness reported | warning | Regulation S-K Item 308, as reported in 10-K Item 9A | Item 9A reports a material weakness in internal control over financial reporting: a reasonable possibility that a material misstatement would not be caught in time. |
| `beneish_above_threshold` | Beneish M-score above screening threshold | info | Beneish (1999) M-score, Phase 7d (ADR-0042) | A screening heuristic computed from this 10-K's figures is above -1.78. It is a reason to read the accounting notes, not a conclusion about them. |
| `restatement_in_xbrl` | Values restated in an amended filing | warning | XBRL as-reported values (10-K/A, 10-Q/A) | An amended filing reports a different value for a period already reported. The earlier figure is kept as reported. |

## Phrase rules

Patterns live in `backend/app/redflags/patterns.py` (compiled regexes, each with an example).
Matching is per sentence; abbreviations (Mr., Inc., U.S., initials) do not end a sentence.

- **Going concern** (10-K, 10-Q and their amendments). A sentence with "substantial doubt … going
  concern" is classified in this order: negation ("no substantial doubt", "did not raise …",
  "alleviated substantial doubt") → no flag; a policy description ("evaluates whether …") → no
  flag; conditional or risk-factor wording ("if …", "could", "may") → `going_concern_risk_language`;
  "… alleviated/mitigated by management's plans" → `going_concern_alleviated`; otherwise
  `going_concern`. The flag quotes the exact sentence and its `paragraph_id`.
- **Material weakness** (10-K Item 9A only). A weakness identified, existing, or controls "not
  effective because of" one. Not flagged: the standard definition ("A material weakness is …"), a
  denial ("did not identify any …"), a hypothetical ("could result in …") or a remediation.
- **Executive departure** (8-K Item 5.02). A departure verb (resign, retire, terminate, step down,
  depart, not stand for re-election) in a sentence of the item's text, after the item title is
  removed. Not flagged: award or agreement terms ("if she resigns for good reason", "vests upon
  retirement") and biographies ("previously served as", "experience … most recently"). Roles
  (CEO, CFO, COO, CAO, President, Director; not "vice president") come from the departure sentence
  itself; none found → `exec_change_unspecified`. Names are never extracted.

## Classification and storage

- An 8-K's items come from the EDGAR filing index (`filings.items`), falling back to the parsed
  item headings (Phase 7c, FR-EX-003). Item codes are full dotted codes, so 5.07 (a shareholder
  vote) can never trigger a 5.02 rule.
- One flag per rule per filing, quoting the first matching paragraph. Source ID:
  `redflag:{TICKER}:{rule_key}:{accession}`. `event_date` is the filing date.
- Changing a rule or pattern bumps `TAXONOMY_VERSION`: detection then adds rows under the new
  version and the API serves only the newest.
