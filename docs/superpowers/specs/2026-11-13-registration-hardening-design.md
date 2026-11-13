# Auth follow-ups — registration hardening (Issue #47, slice 2)

Second slice of #47. Registration (`POST /api/auth/register`) creates an
account and shows its login ID once. Today anyone can create unlimited
accounts, a taken or invalid username crashes the request with a 500, and the
client address used for rate limiting can be forged.

## Owner decision (2026-11-13)

Generous limits, so a whole onboarding session on shared workplace Wi-Fi
still works: at most **30 sign-ups per hour from one network address** and
**200 per day in total**.

## Part A — clear answers and a trustworthy address

**Usernames.** The request is checked against the existing rule (3–24
letters, digits or underscores) before anything is written: 422 with the rule.
A name already taken, in any letter case, is 409 "Username taken"; the
database's unique key on `username_lower` is the source of truth, so a race
between two sign-ups for one name also ends in 409, never 500.

**Client address.** `_client_key` decides which network a request comes from,
for the login limiter and the new sign-up limiter. It used to believe the
`X-Forwarded-For` header from anyone, so a script could make up a new address
per request. It now reads that header only when `SORT_TEST_TRUST_PROXY=1`, set
where a trusted proxy (such as Azure's ingress) sets the header; otherwise it
uses the connection's own address.

## Part B — sign-up limits

`RegistrationLimiter` in `backend/auth/rate_limit.py` keeps the times of
successful sign-ups in memory: per client address within a sliding hour, and
in total within a sliding day. A sign-up is refused with 429 before anything
is written when either cap is reached. Refused sign-ups (429, 409, 422) do not
count.

Each application instance has its own limiter (`app.state`), created in
`create_app`. The counts reset when the process restarts and are not shared
between processes: suitable for the single-instance pilot; a shared store is a
hosting decision (#41).

## Out of scope

Captcha, invite codes, email verification, the deletion flow (slice 3) and
hosting (slice 4).

## Testing

- Usernames: taken (other case) is 409; too short, too long, a space and a
  non-ASCII letter are 422; nothing is created.
- Address: `X-Forwarded-For` is ignored without the setting and used with it.
- Limiter (unit, fake clock): the per-address cap, the hour sliding, the daily
  total across addresses, the day sliding.
- HTTP: the 31st sign-up from one address in an hour is 429; refused sign-ups
  do not count; another address is not affected when the proxy is trusted.
