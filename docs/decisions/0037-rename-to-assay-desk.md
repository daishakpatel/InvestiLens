# ADR-0037: Rename the product from InvestiLens to Assay Desk

- **Status:** Accepted
- **Date:** 2026-10-17
- **Spec refs:** §6 (LGL-001)

## Problem

The product needed a new name. The old name appears in UI copy, docs, package metadata, CI and
config, and some of those places hold identifiers that existing local or deployed data depends
on (database name and user, MinIO credentials and bucket, Render service names, the seed user's
email, browser storage keys). Renaming those would orphan that data or create new deployed
services.

## Decision

The product is now **Assay Desk**: the display name is `Assay Desk`, the slug is `assay-desk`, and
code identifiers use `assay_desk` / `ASSAY_DESK`. The spec moved to `docs/AssayDesk_Spec_v2.md`.
UI copy, docs, package names, CI-only identifiers and observability labels were renamed.
Earlier ADRs keep their content, dates and numbering; only the product name in their prose
changed. Identifiers tied to existing data or deployments (`render.yaml` service names, Postgres
database/user defaults, the Docker Compose project name (which names the volumes), MinIO
credentials, the `investilens-filings` bucket, the seed user's email,
and the `il-*` localStorage keys) deliberately keep the old name until each one is migrated on
purpose.

## Consequences

Users see one consistent name, and no data or deployed service is lost. The cost is a short list of
old-name identifiers left in config, which a search for the old name will still find. Each one
moves when its data or service is migrated (for example, a new Render blueprint or a database
rename with a dump and restore).
