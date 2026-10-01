# Phase 3c — Chat / User Q&A

**Prerequisites:** `14_phase3b_research_report_generation.md` done (reuses its generation
patterns and section content), `13_phase3a_citation_system.md` done.
**Blocks:** `19_phase4d_frontend_report_and_chat.md` (chat UI has nothing to call without
this).
**Full spec sections:** §10.14 (chat feature requirements), §16.8 (example question
walkthrough), §16.9 (prompt-injection defense — applies here too, this is the most
user-exposed surface).

## Objective

Let a user ask free-form questions about a company and get a citation-verified, streamed
answer, using the same retrieval and verification machinery already built.

## Scope

1. **Request flow** (spec §16.8's NVIDIA revenue-growth example is the reference
   walkthrough): question → Phase 2c's intent classifier → retrieval (structured tools +
   vector/keyword search as appropriate to intent) → LLM synthesis → Phase 3a's citation
   verification → response.
2. **Multi-turn context:** maintain a bounded conversation window per `chat_sessions` /
   `chat_messages` row (from Phase 0b's schema); resolve follow-ups ("and last quarter?")
   using the prior turns.
3. **Streaming:** implement `POST /chat/stream` (SSE, already contracted in Phase 0c) so
   tokens and citations appear progressively rather than all at once.
4. **Tool-trace panel data:** record which tools ran for this answer (e.g. "Checked: XBRL
   revenue FY2023–25, 10-K MD&A, Q4 release") and return it alongside the answer — this uses
   the tool-call logging already built in Phase 2c.
5. **Abstention (HAL-003):** if retrieval comes back empty or all candidate claims fail
   verification, return a structured "I couldn't find evidence in the ingested sources for
   this" response — not a vague hedge, an explicit, testable outcome.
6. **Scope guard:** detect and gracefully refuse out-of-scope requests — buy/sell/hold advice,
   questions about companies that haven't been ingested — with a helpful redirect rather than
   a bare refusal.
7. **Suggested follow-up questions:** generate a few from the current report/answer content
   (cheap model call is fine here).
8. **Feedback:** implement `POST /chat/messages/{id}/feedback` (thumbs up/down + optional
   reason), stored in `chat_messages.feedback`/`feedback_reason` — this feeds Phase 5b's
   golden-set growth loop later.
9. **Cost/latency logging:** every chat turn logged like any other LLM call (tokens, cost,
   latency, prompt version) via the existing `llm_calls` pattern.
10. **Prompt-injection defense:** reuse Phase 2c's untrusted-content wrapping without
    exception — chat is the most directly user-exposed surface, so re-run the red-team test
    set from Phase 2c against the full chat flow, not just raw retrieval.

## Out of scope for this file

No new retrieval logic (reuse Phase 2c entirely) and no new verification logic (reuse Phase 3a
entirely) — this file is the orchestration and conversation-state layer on top of both, plus
streaming and feedback.

## Definition of Done

- [ ] A metric question ("What was NVIDIA's FY2025 revenue?") is answered from structured data
      with an exact match to `financial_metrics`, not via document retrieval
- [ ] A qualitative question ("Why did gross margin decline?") returns a cited, verified answer
      using the same pipeline as report generation
- [ ] A follow-up question correctly uses prior conversation context
- [ ] An out-of-scope question ("should I buy NVDA?") is refused with a helpful redirect, not a
      bare error
- [ ] A question with no supporting evidence returns an explicit abstention response, not a
      hallucinated answer
- [ ] `POST /chat/stream` streams tokens and resolves citations as the answer completes
- [ ] Feedback submission is stored and retrievable
- [ ] The prompt-injection red-team set, run against full chat (not just retrieval), does not
      change model behavior
