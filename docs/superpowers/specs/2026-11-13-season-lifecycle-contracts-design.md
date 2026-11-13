# Seasons — private history, lifecycle status and remaining tests (Issue #23, slice 4)

Fourth and last slice of #23. It builds on the season clock, the launch and
the close. It adds the two read-only contracts other work needs and the tests
#23 still asks for.

## Part 1 — account-private history

Decision 12 keeps completed and launch-ended Pre-Season attempts for a profile
tab named "pre season history", private to the account: no other-player
access, server-side ownership checks, and no automatic administrator
exception.

`backend/ranked/history.py`: `account_history(conn, account_id, phase=None)`
returns the account's settled attempts, newest first. Each entry has the
attempt id, the season's `phase` and `label`, the attempt `mode`,
`final_outcome`, `raw_score`, `adjustment`, `points_before`, `points_after`,
`badge_before`, `badge_after` and `settled_at`. `phase` limits it to
`pre_season` or `official`.

`GET /api/ranked/history?phase=...` returns that list for the signed-in
account. The account comes only from the session: the request has no way to
name another account, and the owner account gets no exception. An entry ended
at launch has `final_outcome` `launch_reset` and a zero adjustment, which
distinguishes it from a completed one; nothing is invented for answers that
were never given.

The tab itself is page work (#10/#16).

## Part 2 — lifecycle status

`GET /api/ranked/season` returns the current season for the signed-in
account: `season_id`, `phase`, `label`, `status` (`open`, `finishing`,
`closed`, `frozen`), `closes_at` and `points_final` (true once frozen). The
current season is the newest one. With no season at all it answers 404.

This is the contract for standings (#12) and tie-breaks (#24): points are
final when `points_final` is true. Prize standings stay provisional after that
until those issues finalize them; #23 does not model prizes.

**Launch fact for #27.** `seasons.official_launch(conn)` returns the official
season's id, label and `opened_at`, or `None` before launch. #23 writes no
outbox row: outbox rows are per recipient and need the verified email and
consent that #27 owns. The official season row is the durable, exactly-once
launch marker that #27 reads to create its own messages.

## Part 3 — remaining tests

- Launch with an attempt in connection grace.
- An outage confirmed before the freeze: affected attempts settle at zero and
  the season still freezes.
- An outage confirmed after the freeze (late evidence): nothing is voided and
  no balance changes.

## Out of scope

The history tab and any page work (#10/#16); prize standings and their
finalization (#12/#24); reminder delivery (#27); owner second factor
(#11/#13).

## Testing (TDD, live scratch PostgreSQL)

- History: 401 without a session; own entries only; the phase filter; a
  launch-ended entry distinct from a completed one; the owner cannot read
  another account's history; an unknown phase is 422.
- Season status: 401; each status value; `points_final`; 404 with no season.
- `official_launch` before and after launch.
- The three tests in Part 3.
