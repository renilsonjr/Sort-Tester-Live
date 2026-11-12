# Ranked attempt engine — page capability (Issue #8, slice 4)

Fourth slice of the ranked attempt engine. It builds on slice 3
(`2026-11-12-ranked-engine-quit-outage-design.md`) and closes the limit slices
2 and 3 recorded: until now any request carrying the account session and the
attempt id could continue an attempt. The decision record (Decision 6) and the
security/operations design (Q8) require that only the original still-running
page can.

## Design

The attempt is bound to a random page-instance capability.

- **Issue:** when an attempt starts, the server generates a random token
  (`secrets.token_urlsafe(32)`) and returns it once, in the start response.
  The page holds it in memory only.
- **Store:** migration `0015` adds `attempts.page_capability_sha256 bytea
  NULL`. Only the SHA-256 of the token is stored, written in the same
  transaction that creates the attempt. The raw token is never stored or
  logged.
- **Present:** every later attempt request (current question, answer, advance,
  heartbeat, quit) carries the token in the `X-Attempt-Capability` request
  header. It is not accepted from a cookie, the URL or the body.
- **Check:** after the session and ownership checks, the server compares the
  SHA-256 of the presented token with the stored one in constant time. A
  missing or wrong token, or an attempt with no stored capability, is refused
  with 403 before any engine call. A refused request therefore never counts as
  a heartbeat or a return within grace.

Consequences, with no further code:

- A reloaded page or a second tab has the session cookie but not the token. It
  cannot continue, answer, advance, keep alive or quit the attempt. The
  attempt goes silent and ends as a `disconnect` at the existing grace
  deadline, with no Quit penalty.
- The one-unfinished-attempt lock is unchanged, so such a page cannot start a
  replacement either (409).
- A start response lost in transit leaves an attempt nobody holds the token
  for; it ends the same way.

## Code shape

- `backend/ranked/capability.py`: `new_token()`, `hash_token(token)`, and
  `matches(conn, attempt_id, token) -> bool`.
- `engine.start_attempt` gains an optional `page_capability` argument and
  stores its hash with the attempt. Its return value is unchanged. An attempt
  started without one has no stored capability and cannot be driven over HTTP.
- `backend/routers/ranked.py`: the start endpoint generates the token, passes
  it to the engine and returns it as `capability`; the ownership helper also
  requires the header on the five attempt endpoints.

## Limits

This enforces possession of a page-memory secret. A user can copy it out of
their own running browser; it is not proof of a device or of a human. The
static site is not wired to the backend yet, so this slice delivers and tests
the server side only.

## Out of scope

Promotion entry, phase hooks, the fifteenth-question rule, loss IDs and flags
(#25), WebSocket transport, front-end wiring.

## Testing (TDD, live scratch PostgreSQL)

- Engine: starting with a capability stores its hash, not the token; `matches`
  is true for the right token and false for a wrong, empty, missing or
  non-ASCII token and for an attempt started without one.
- HTTP: start returns a capability; a full attempt works with the header; each
  of the five endpoints answers 403 without it and with a wrong one; a refused
  heartbeat does not move `last_heartbeat_at`; ownership (404) and
  authentication (401) still take precedence; migration 0015 upgrades and
  downgrades cleanly.
