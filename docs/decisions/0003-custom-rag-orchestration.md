# ADR-0003: Custom RAG orchestration, not LangChain

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §16, §20 (AI/ML stack)

## Problem

The RAG pipeline has finance-specific needs: intent routing between structured data and
retrieval, table-aware chunks, parent-child retrieval, RRF fusion, abstention, backend-issued
source IDs, and prompt-injection defense. Frameworks like LangChain hide those steps behind
abstractions that are hard to test, change often, and obscure exactly what the model saw.

## Decision

Write the orchestration ourselves in `backend/app/rag/`: query planning, retrieval, fusion,
reranking, context assembly, and prompt construction as small, typed, individually tested
functions. Focused libraries are allowed for leaf tasks (SDK clients, a cross-encoder); the
orchestration itself is ours.

## Consequences

Every step is inspectable, unit-testable, and logged (`retrieval_logs`), which supports
reproducibility (NFR-010) and gives a stronger engineering story. We write and maintain more
code, and we don't get framework integrations for free. That's acceptable because the pipeline
is narrow and provider access already goes through our own interfaces.
