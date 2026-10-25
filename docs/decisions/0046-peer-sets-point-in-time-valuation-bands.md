# ADR-0046: Explicit peer sets, point-in-time multiples and minimum sample sizes for bands

- **Status:** Accepted
- **Date:** 2026-10-24
- **Spec refs:** §37.1–§37.2, §10.7, §12, Appendix H (FR-PS-001 … FR-PS-014, DR-PS-001 … DR-PS-004)

## Problem

A multiple only means something against the company's own history and against comparable
companies. Phase 6a suggested peers loosely and compared current fiscal-year values. Five things
had to be decided:
- **Who counts as a peer.** It must be explainable, and not left to a model.
- **How to compute a multiple at a past date without look-ahead.** A 10-K is filed weeks after the
  year it reports, and later restatements must not reach back.
- **How to line up peers whose fiscal years end in different months.**
- **When a percentile is too thin to show.**
- **The audit's EV/EBITDA gap for AMD and Intel.** Neither tags a total depreciation &
  amortization any more.

## Decision

**Peer sets are stored and explained.**
- `peer_sets` and `peer_set_members` (with a rationale per member) hold one `system_default` per
  company and each user's private sets.
- **The default rule** (`comparison/peers.py:default_peers`) is deterministic: same SIC code,
  same reporting currency, market cap 0.25×–4× of the target's (configurable), the target
  excluded, nearest market cap first on a log scale, ties by ticker, at most 8. The rationale reads
  "same SIC 3674; market cap 1.8× target". It is rebuilt with prices and in `build_metrics.py`
  after every company's market cap is fresh.
- **Fewer than three members is "insufficient peers"**, and peer statistics are hidden.
- **User sets** hold 1–12 known tickers. Unknown tickers are named with a pointer to the
  watchlist, never dropped. Other users get 404.

**Multiples are point in time** (`finance/point_in_time.py`).
- For a date D only facts filed on or before D are used, with the latest-filed value per period.
- TTM flows end at the latest quarter end D's filings report: the twelve-month value, or prior FY
  + YTD − prior YTD. Each period takes the first concept-map tag that reports it, so a filer that
  switches tags (NVIDIA's revenue) still has a TTM. Balances are the instants at that quarter end.
- The share count is the latest one dated and filed by D, moved across later splits.
- **The multiples:**
  - P/E = market cap ÷ TTM net income, which avoids mixing share bases across a split.
  - P/S, EV/Revenue, EV/EBITDA, EV/FCF.
  - P/B: not applicable for banks, because price to tangible book needs goodwill and intangibles
    mapped.
  - FCF yield and earnings yield.
- **Enterprise value** = market cap + short- and long-term debt + minority interest + preferred −
  cash − short-term investments.
- **A multiple is `not_meaningful`** when its denominator is zero or negative, or the multiple
  exceeds 200× (a near-zero denominator such as Intel's FY2025 earnings). It is never drawn,
  never ranked, and never stored as a negative number. Yields stay meaningful when negative.

**What is stored.**
- `valuation_history` holds every multiple at the last five fiscal year ends and the latest close,
  each row with its price, share count and every figure's source IDs.
- A year-end value therefore uses TTM through the last reported quarter, because the 10-K for that
  year was not yet filed.
- The latest-close rows the header reads now come from the same engine, so the header and the
  bands agree. Fiscal-year rows keep fiscal-year figures, labelled as such.

**Calendarization.** Peer statistics compare each peer's TTM multiple at its own latest close. A
twelve-month window ending at each company's latest quarter puts different fiscal year ends on one
calendar basis. A peer without one is excluded and listed with the reason; this covers fewer than
four quarters, a loss, or no prices. The fiscal-year comparison (`/compare?peer_set_id=`) keeps
the 6a calendarization.

**Minimum samples.**
- An own-history band needs three fiscal year ends with a value; a percentile needs five values
  (five year ends + today).
- Peer statistics need three peers with a value.
- Below that the field is null with a reason, and every percentile reports its `n`.

**Wording.** Labels are positional only ("in the top quartile of its 5-year range", "18% above
peer median"). The advice guard (`citation/advice.py`) now rejects valuation calls (cheap,
expensive, undervalued, overvalued, bargain, richly or attractively valued) in generated
commentary, and a test runs every band template through it.

**EV/EBITDA for AMD and Intel.** Company overrides declare D&A as a composite of the parts each
filer tags. The parts are summed per period and filing only when all of them are present, and
the composite is treated as one more tag.
- **Intel:** `Depreciation` + `AmortizationOfIntangibleAssets`; FY2025 is 10,757 + 949 = $11,706M,
  the two lines of its cash-flow statement.
- **AMD:** `OtherDepreciationAndAmortization` + `AmortizationOfIntangibleAssets`; FY2025 is
  750 + 2,300 = $3,050M. AMD's statement shows 750 + 2,254, because its acquisition-intangibles
  line uses AMD's own tag, which companyfacts does not carry. That counts $46M (1.5%) twice; the
  alternative pairing would miss $183M.

## Consequences

- Bands are reproducible and cite every input. Losses never produce a misleading number. AMD and
  Intel now have EBITDA and EV/EBITDA.
- With only five companies in the dev universe, every default set is "insufficient peers": NVIDIA's
  same-SIC peers are 6–12× smaller. Peer statistics there need a user's own set until the universe
  grows (TODO).
- Some year-end values are `missing_input` where a filer's tags leave a gap:
  - NVIDIA's FY2021 capex is not in companyfacts, so its FY2022–FY2024 EV/FCF is missing;
  - AMD tagged no D&A before 2022.
- The 200× cutoff is a judgement call, chosen so a P/E on near-zero earnings is not ranked.
- Revisit if forward multiples (licensed estimates) or price-to-tangible-book for banks are wanted.
