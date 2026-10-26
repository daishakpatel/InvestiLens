# Evaluation report

Generated 2026-10-25T22:25:50+00:00 from `4049bcc733dfe4bc5d5e6557f76ad9327a9fd46b` (uncommitted changes) by `make eval-report`.

- **LLM:** mock (FakeLLM (deterministic))
- **Dataset:** golden_v0, 106 cases + 11 injection inputs
- **Prompts:** chat_synthesis `chat_synth@8a38c682`, report `report_v3`, judge `judge_v1`
- **Data:** offline fixtures for NVDA, AAPL, JPM

| Metric | Value | Wilson 95% interval | Count |
|---|---|---|---|
| citation_validity | 100.0% | 96.2% to 100.0% | 98/98 |
| number_match | 100.0% | 90.1% to 100.0% | 35/35 |
| correct_abstention | 58.3% | 38.8% to 75.5% | 14/24 |
| false_abstention | 7.3% | 3.4% to 15.1% | 6/82 |
| retrieval_hit_at_5 | 64.6% | 53.8% to 74.1% | 53/82 |
| retrieval_mrr | 0.4683 | — | n=82 |
| injection_resistance | 81.8% | 52.3% to 94.9% | 9/11 |

## Latency

| Path | p50 | p95 | n |
|---|---|---|---|
| chat answer (first token = full verified turn) | 129 ms | 3131 ms | 112 |
| report generation | 2981 ms | 28509 ms | 3 |

Single-user timings with the mock LLM on the machine that ran the report, so they exclude model time; the load test (load/locustfile.py) has not been run against a deployed stack.

## Definitions

- **citation_validity:** Share of citations on answered questions whose source ID resolves through the source resolver and whose quoted text, if any, is a verbatim substring of it.
- **number_match:** Share of numbers in answered text that match a value in the sentence's cited sources within the verifier's relative tolerance.
- **correct_abstention:** Share of questions that must be declined (advice, forecasts, unknown companies, injections) that the system declined.
- **false_abstention:** Share of answerable questions that the system declined (lower is better). Reported beside correct abstention because either alone hides the trade-off.
- **retrieval_hit_at_5:** Share of retrieval questions with at least one expected document in the top 5 retrieved documents.
- **retrieval_mrr:** Mean reciprocal rank of the first expected document (no interval: not a proportion).
- **injection_resistance:** Share of prompt-injection inputs (golden-set injections plus the security corpus, asked as questions) that were declined or answered without complying.

## What these numbers do not show

- Writing quality and faithfulness of a real model: the mock run uses a deterministic fake that quotes its evidence, so it measures retrieval, verification and abstention only.
- Retrieval quality with real embeddings: mock embeddings are hashes, so hit@5 and MRR here are plumbing checks, not semantic quality (ADR-0010, ADR-0020).
- Injection planted inside filings: covered by the sanitiser unit tests (DP-004), not this rate, which asks the injections as questions.
- Earnings briefs, guidance extraction, governance facts and thesis drafts: each has its own recorded-response tests, but no golden questions.
- Companies beyond the three seed tickers, non-US filers, and live price or news data.
- Latency under concurrent load or with a real model: these are single-user timings on the machine that ran the report.
