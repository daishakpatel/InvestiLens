"""Filing diff, earnings reaction, and management-language tracking (spec §37.3-§37.5, Phase 6b).

Everything here is deterministic Python over already-parsed `document_chunks`; the only LLM use is
an optional yes/no adjudication of borderline alignments (ADR-0027).
"""
