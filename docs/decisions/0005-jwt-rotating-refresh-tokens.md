# ADR-0005: JWT access tokens with rotating refresh tokens

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §26.1 (AUTH-001…006), §29

## Problem

The SPA needs authentication that is stateless on the hot path, resists token theft
(especially through XSS), and supports logout and revocation.

## Decision

- **Access token:** a JWT (HS256, `JWT_SECRET`) with a 15-minute lifetime and claims `sub`,
  `exp`, `iat`, `jti`. Sent as `Authorization: Bearer`. The frontend keeps it in memory only,
  never in `localStorage`.
- **Refresh token:** an opaque random value (256-bit), not a JWT, with a 14-day lifetime. Only
  its SHA-256 hash is stored in `refresh_tokens`. It lives in an `httpOnly; Secure;
  SameSite=Strict` cookie scoped to the refresh endpoint path.
- **Rotation:** every refresh issues a new token and revokes the old one. Tokens belong to a
  family, so if a revoked token is presented again, the whole family is revoked (theft
  detection).
- **Passwords:** Argon2id (`argon2-cffi`). Login is rate-limited with backoff.
- **Library:** PyJWT, not `python-jose` (which is poorly maintained).

## Consequences

Stolen access tokens expire quickly. Refresh tokens can't be read by JavaScript, and reuse is
detected. Logout and revocation work by deleting refresh-token families. Costs: one DB lookup
per refresh (not per request) and the added work of family tracking. HS256 is enough for a
single issuer and verifier; switch to asymmetric keys if another service ever needs to verify
tokens.
