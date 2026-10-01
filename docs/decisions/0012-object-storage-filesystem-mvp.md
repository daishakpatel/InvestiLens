# ADR-0012: Filesystem object storage for MVP, S3/MinIO behind the same interface

- **Status:** Accepted
- **Date:** 2026-09-30
- **Spec refs:** §21 (ING-008 raw preservation), §20, §31

## Problem

Ingestion must always preserve raw source documents so reprocessing never re-downloads
(ING-008). The spec names MinIO locally and S3 in production, but standing up MinIO plus an
S3 client (boto3) adds infrastructure and a heavy dependency before any ingestion logic exists.

## Decision

Introduce an `ObjectStorage` interface with a `FilesystemObjectStorage` backend for MVP
ingestion: raw filings are written under `storage_dir` (default `.storage`, gitignored) with a
deterministic key `sec/{cik}/{accession}/{document}`. A `MinioObjectStorage`/S3 backend
implementing the same interface is wired in Phase 5d (deployment); a MinIO service is included
(commented) in `docker-compose.yml` for that step. No code outside the backend class changes
when we switch.

## Consequences

Ingestion runs offline and in CI with zero extra infrastructure, and raw bytes are preserved for
reprocessing. The tradeoff is that local filesystem storage isn't shared across hosts — fine for
single-node MVP and tests, and replaced by object storage in deployment. Because access is behind
one interface, the swap is isolated and low-risk.
