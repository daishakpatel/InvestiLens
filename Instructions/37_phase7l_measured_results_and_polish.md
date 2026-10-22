# Phase 7l — Measured Results, Hosted Demo, Limitations, README Consistency, Thin Vertical Slice

**Prerequisites:** 7a–7k done (or, for items marked **early**, can start at any time). Phase 5b
(eval framework), 5d (devops) done.
**Blocks:** nothing. This is the last file in Phase 7 and the one that turns the project from "a
lot of features" into "a project someone can verify in five minutes".
**Full spec sections:** §18 (evaluation), §36 (MVP DoD), `TODO.md`. Requirement IDs:
`NFR-ME-001` … `NFR-ME-012`.

## Objective

A resume project is judged in minutes by someone who will not read the code first. They look at the
README, try the demo, and look for evidence that the claims are real. This file closes four gaps:

1. **Numbers are claimed, not measured.** The README and docs state quality targets, but no
   committed, reproducible result backs them.
2. **No hosted demo.** A reader cannot try it without Docker, keys and a database.
3. **Limits are not written down.** Honest limits increase credibility; silence reads as
   ignorance.
4. **Docs drift.** README, `docs/`, and the code disagree in places (counts of tests, features
   listed, phase status).

Part A can be started **early** (right after Phase 5b); do not wait for 7k.

## Part A — Live evaluation numbers (early)

1. **Eval run on a schedule, results committed.** The nightly `run_eval_suite` exists. Add
   `make eval-report`, which runs the golden set (`backend/tests/eval/`) against the **mock** LLM
   (deterministic, CI-safe) and optionally the **live** LLM (`EVAL_LIVE=1`, manual), writing
   `docs/eval/latest.json` and `docs/eval/latest.md` with: date, git SHA, model name and version,
   prompt versions, dataset version, n cases, and each metric below.
2. Metrics to report, each with its definition in the file header:
   - citation validity rate (share of AI claims whose source ID resolves and whose quoted text is
     a verbatim substring)
   - number-match rate (share of numbers in AI text matching the cited metric within tolerance)
   - abstention rate on unanswerable questions (target high) and false-abstention rate on
     answerable ones (target low) — both are required; reporting one alone hides the trade-off
   - retrieval hit@5 / MRR on the retrieval question set
   - injection-resistance rate on the adversarial fixtures
   - latency p50/p95 for report generation and chat first token (from the load test)
3. **Confidence intervals.** With small n, report a Wilson 95% interval, not a bare percentage.
   Never write "100%" for a sample under 100 without the interval beside it.
4. **Regression gate.** CI fails if citation validity or number-match falls below a threshold
   recorded in `docs/eval/thresholds.json`, or if the report's `git SHA` is stale relative to
   the code touching prompts/citation (a freshness check on changed paths). Lowering a threshold
   requires an ADR line in the PR.
5. README shows a small results table linked to `docs/eval/latest.md` with the date. **The README
   must never contain a number that is not in `latest.json`** (checked in 7l Part D).
6. Record what the golden set does **not** cover (see Part C).

## Part B — Hosted demo

7. Provide a read-only public demo mode: `DEMO_MODE=1` seeds NVDA, AAPL, JPM from fixtures (no
   external keys), disables registration of real accounts, disables LLM calls except against
   **recorded** responses, and shows a banner "Demo: fixture data as of {date}. Not investment
   advice." Writes (alerts, theses) work for a shared demo user in a sandbox DB that resets nightly.
8. Deployment target: pick the cheapest option compatible with Phase 5d's compose setup (a single
   small VM with Docker Compose behind Caddy/HTTPS, or a managed container platform + managed
   Postgres with pgvector). Write the choice and monthly cost in an ADR (ADR-0050). Put the
   deploy steps in `docs/deploy-demo.md` and make `make deploy-demo` reproducible.
9. Abuse controls for a public URL: rate limit per IP, request size caps, chat length caps, LLM
   disabled in demo (recorded answers only), and secrets absent from the image. Add a smoke test
   hitting the deployed health endpoint in CI after deploy.
10. Include a guided path: `/demo` landing page with three one-click scenarios — (1) NVDA overview
    with red flags and earnings quality, (2) a cited research question with the citation drawer,
    (3) a filing diff. Each scenario must work from recorded data with no network.

## Part C — Limitations document

11. `docs/limitations.md`, linked from the README, with sections: **Data** (sources, delays, what
    is sample data such as news), **Coverage** (3 seed companies; sector-specific gaps; US
    filers only), **Models and heuristics** (Beneish/Altman/Piotroski calibration, topic
    taxonomy is lexicon-based, red flags are reported events), **AI** (what is verified, what
    isn't; abstention behavior; known failure modes seen in eval), **Security/privacy** (what is
    stored, what is logged), **Not built** (consensus estimates, transcripts, insider trades,
    options data). Each limitation is a concrete sentence, not boilerplate.
12. A "Known issues" list pulled from `TODO.md`, each with status and a link to the task file that
    would address it. Remove items from the list as they are fixed.
13. A section "How I'd validate this with a real analyst", 5 bullets, naming specific checks
    (for example: pick 10 filings, compare extracted guidance to the press release by hand).
    This signals judgment without claiming validation that has not happened.

## Part D — README and docs consistency

14. Write `scripts/check_docs_consistency.py` (run by `make check`) that fails when:
    - a requirement ID referenced in tests/docs does not exist in the spec appendices;
    - the README lists a feature whose route is missing from `docs/openapi.json`;
    - any numeric claim in the README (percentages, counts) is not present in `docs/eval/latest.json`
      or in a generated stats file (test count, endpoint count, ADR count);
    - an ADR number is duplicated or skipped;
    - a task file named in `Instructions/00_START_HERE.md` doesn't exist.
15. Generate the stats (test count, endpoint count, ADR count, LOC by area) into
    `docs/generated/stats.json` via `make stats`; the README embeds them by reference, not by
    hand-typed numbers.
16. README structure (top to bottom, no more than ~120 lines): one-sentence pitch; screenshot
    or GIF; live demo link; "what it does" in 6 bullets; the measured results table; architecture
    diagram; run locally in 3 commands; link to `docs/limitations.md`; link to the task-file
    method. Remove the stale feature lists.
17. Update `Instructions/TODO.md`: close items delivered by Phase 7 with the task file reference
    (e.g. "quarterly/TTM not persisted → 27"), leave unbuilt ones listed.

## Part E — Thin vertical slice (the five-minute path)

18. Choose one end-to-end scenario and make it flawless, with a Playwright test that runs it
    against the demo build:
    1. open NVDA overview (quarterly/TTM toggle, red-flag panel, earnings quality);
    2. ask "What changed in risk factors vs last year?" and see a cited answer; open the drawer;
    3. open the latest earnings brief (7j) with guidance vs actual (7i);
    4. create a thesis KPI (7k) that triggers, see the in-app notification.
19. Record a 60-second screen capture of exactly this path (`docs/media/demo.gif`), generated
    from the Playwright run for reproducibility, and reference it in the README.
20. Fix every console error and layout shift found while recording; the test asserts no
    unexpected console errors on the path.

## Out of scope

Paid hosting tiers, custom domain branding, analytics or tracking scripts, marketing site,
user-acquisition features, and any new analytics feature. If a gap is found while recording,
file it in `TODO.md`; don't build it here.

## Docs to update in the same PR

README, `docs/limitations.md`, `docs/deploy-demo.md`, `docs/eval/*`, `docs/generated/stats.json`,
`Instructions/TODO.md`, spec Appendix H, ADR-0050 (demo hosting + cost).

## Definition of Done

- [ ] `make eval-report` writes `docs/eval/latest.{json,md}` with date, SHA, model, prompt and
      dataset versions, and every metric above with Wilson 95% intervals
- [ ] CI fails when a threshold in `docs/eval/thresholds.json` is breached (demonstrated with a
      deliberately broken branch recorded in the PR description)
- [ ] False-abstention and correct-abstention rates are both reported
- [ ] Public demo URL is live, uses recorded LLM responses only, shows the demo banner, and passes
      the post-deploy smoke test; monthly cost documented in ADR-0050
- [ ] Rate limits and request-size caps are active in demo mode (test)
- [ ] `docs/limitations.md` covers all six sections with concrete statements and is linked from the
      README
- [ ] `scripts/check_docs_consistency.py` runs in `make check` and each rule has a failing-case test
- [ ] No hand-typed numeric claim remains in the README (script proves it)
- [ ] README ≤ ~120 lines, in the specified order, with the demo link, GIF and results table
- [ ] The vertical-slice Playwright test passes against the demo build with no console errors
- [ ] `TODO.md` updated to reflect what Phase 7 closed
- [ ] `make check` clean
