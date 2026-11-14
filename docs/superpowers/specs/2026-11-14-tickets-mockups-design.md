# Support ticket mockups (Issue #16, slice 4)

Last slice of #16. #15 left Support → Tickets as an empty placeholder with a
Create ticket button. This slice gives it the ticket list, the create form,
the ticket detail and the retention states that Decision 8 requires.

Issue #26 owns the real feature and is blocked by this issue among others, so
these screens are one of its prerequisites. Nothing here implements it.

This is a design for a mockup only. No app file (`index.html`, `src/`,
`backend/`) changes, and nothing here is a completed feature.

## The rules these screens have to carry

From Decision 8:

- Support holds Tickets and nothing else. No further player Support options
  are approved.
- A ticket exists only because a player asked for one. The system never
  opens one by itself, and a connection flag is not a ticket.
- A ticket carries the attempt and its connection events; a written
  description is optional.
- Players see only their own tickets. Tickets never appear on profiles or
  leaderboards.
- A ticket closes as network instability, or as insufficient evidence without
  any accusation, or stays open for follow-up. **None of these changes points
  or access.**
- A closed ticket's description and its unshared connection details are
  deleted 15 days after closure.
- A connection log shared with another case is kept while any linked case is
  open, then deleted 15 days after the last linked case closes.
- The screens show either the deletion date or the fact that shared evidence
  is held for an open linked case.

## Owner choices (2026-11-14)

| Question | Choice |
|---|---|
| Showing the 15-day rule | The full rule once at the top of the list, and a short line on each closed ticket: its deletion date, or that it is held for a linked open case |
| Choosing the attempt when creating a ticket | A dropdown of the player's attempts, with the optional description and a note of what is sent along |

Options not chosen: a retention line repeated in full on every ticket, the
retention detail hidden behind a disclosure, attempt cards as the picker, and
the most recent attempt preselected.

Each dropdown option names the attempt's date and what happened, not only its
id, so the player can recognise the right one.

## Screens

Added to the existing `mockups/entry-navigation.html`, reached from Profile →
Support. Fictional data only.

1. **Ticket list.** The retention rule at the top, then one open ticket, one
   closed as network instability showing its deletion date, and one closed as
   insufficient evidence whose evidence is held for a linked open case.
   Create ticket.
2. **Empty list.** For a player with no tickets, saying Support opens one
   only when they ask.
3. **Create ticket.** The attempt dropdown, the optional description, and a
   note naming what is sent with the ticket and who can see it.
4. **Ticket sent.** Confirmation, with the reminder that this changes no
   points and no access.
5. **Open ticket detail.** What was sent, and that the evidence is kept while
   the case is open.
6. **Closed ticket detail.** The closure outcome and the date its description
   and connection details are deleted.
7. **Loading and error.**

## Limits

- **Nothing about anyone else's case.** Where evidence is held because of a
  linked open case, the screen says only that a linked case is open: never
  whose, never which.
- No closure accuses anyone. "Not enough evidence" ends a case; it is not a
  suspicion, and the screens never imply one.
- Every state says that Support changes no points and no access.
- Support holds Tickets only.
- The empty state states that the system never opens a ticket by itself.
- No real names, employee IDs or email anywhere; no ticket is visible from a
  profile or the leaderboard.
- Dates are written as "example date"; attempt ids, outcomes and descriptions
  are invented.

## Checks

- **Readable labels.** Every control, status and outcome is named in text.
- **Phone layout.** Checked at 320 px and 375 px: nothing cut off, no
  sideways scroll, and the retention sentences wrap cleanly.
- **Keyboard and focus.** The dropdown, the description field and both
  buttons are reachable with Tab, work with Enter, and show a visible focus
  outline.
- **Not colour alone.** Open and closed, and each closure outcome, are named
  in words; the status pill's colour is secondary.

## Recording the review

1. Show the owner each screen in a browser at phone size.
2. Post one comment on #16 listing the approved screens and the choices.
3. Tick box 5 when this slice merges, and box 6 with it: box 6 is the
   mobile, keyboard, loading, empty, error and privacy review across every
   slice, and this is the last one.

## Delivery

Branch `codex/tickets-mockups`, opened as a pull request for review.

**Ordering note:** this slice waited for PR #99 (slice 3), because both edit
the same mockup file. #99 merged first, and this branch was then rebuilt on
`codex/ranked-mode`, so the two never raced on that file.
