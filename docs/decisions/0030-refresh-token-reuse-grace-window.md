# ADR-0030: A short grace window for concurrent refresh-token use

- **Status:** Accepted
- **Date:** 2026-10-11
- **Spec refs:** §26.1, AUTH-002; amends ADR-0005

## Problem

ADR-0005 revokes a token family when a rotated refresh token is presented again. Two things were
wrong in practice. First, the revocation never took effect: the request that detected the reuse
raised before committing, so the write was rolled back with the 401 and the stolen session lived
on. Second, once that is fixed, an ordinary event looks exactly like theft: a browser restoring
several tabs sends the same cookie from each, the first rotates it, and the rest arrive a few
milliseconds later holding a token that has just been revoked. Enforcing the rule strictly would
sign the user out of every tab each time they reopened the browser.

## Decision

`POST /auth/refresh` commits whatever a rejected refresh wrote before it returns the 401. A
revoked token is treated as a concurrent refresh, not reuse, only when all of these hold: it was
revoked by rotation (it has a successor), that happened within
`REFRESH_REUSE_GRACE_SECONDS` (default 10; 0 disables), and the successor is still active. It
is then issued its own new token in the same family, and its record is left untouched so the
window cannot be extended. Anything else, including a token whose successor has been used or
whose family was revoked by logout, is reuse and revokes the family. The token row is read
`FOR UPDATE`, so simultaneous requests take turns and the second sees the first's rotation.

## Consequences

Reuse detection is now real, and multi-tab session restore keeps working. The cost is a
ten-second window in which a thief who replays a just-rotated token gets a parallel session
without tripping detection; it ends at logout, password reset, or the next detected reuse, all
of which revoke the family. This is the same trade Auth0 and others make with a "reuse
interval". A family can briefly hold more than one active token. Revisit if sessions gain a
device list (each tab's token would show as a session), or if the window proves longer than
real browsers need.
