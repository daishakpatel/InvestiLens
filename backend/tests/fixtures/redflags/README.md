# Red-flag fixtures (Phase 7e)

| File | Source | Used for |
|------|--------|----------|
| `nvda_8k_507.htm.gz` | Real: NVIDIA 8-K, accession 0001045810-26-000056, filed 2026-06-30, Item 5.07 (shareholder vote) | Must yield **no** executive-departure flag (FR-RF-004, the old 5.0x item collision) |
| `intc_8k_205.htm.gz` | Real: Intel 8-K, accession 0000050863-24-000147, filed 2024-10-31, Items 2.02, 2.05, 9.01 | `restructuring` (Item 2.05) |
| `synthetic_8k_402.htm.gz` | **Synthetic**: written for tests, labelled in its text (DR-EX-003). NVIDIA has filed no Item 4.02 8-K. | `non_reliance` (Item 4.02) with the right filing and date |

The real files were copied from the dev object store (originally fetched from SEC EDGAR by the
ingestion pipeline). The NVIDIA 5.02 8-K and the synthetic NT 10-K / NT 10-Q come from
`tests/fixtures/nvda/` via `MockSecSource`.
