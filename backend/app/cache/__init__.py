"""Redis caching (§25.3, CACHE-001..005, ADR-0024).

A thin read-through cache behind a small interface. The cardinal rule is CACHE-005: a cache
error never fails a request — every Redis operation is wrapped so that on any failure the loader
(the DB read) runs and the request succeeds. Disabled by default (`cache_enabled`), so tests and
local dev hit the DB directly and deterministically.
"""
