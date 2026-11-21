# Quitting and lost connection mockups (Issue #17, slice 3)

Third slice of #17. It covers every way a Ranked attempt ends without the
player finishing it: quitting on purpose, losing the connection, reloading
the page, and a server outage.

Remaining after this: prize tie-breaks.

This is a design for a mockup only. No app file (`index.html`, `src/`,
`backend/`) changes, and nothing here is a completed feature.

## What makes this slice different

Four of these screens show the same frustration from different angles, and
what separates them is **how much the player is penalised**:

| How it ended | What it costs |
|---|---|
| Quit on purpose | The partial score, **plus 10 points** |
| Connection lost, grace expired | The partial score, **no extra penalty** |
| Page reloaded | The attempt ends; the partial score stands |
| Confirmed server outage | **Nothing.** The attempt is voided, zero adjustment |

If the screens do not make that ladder obvious, all four read as "I lost my
points", and the one that costs nothing looks the same as the one that costs
ten.

## The rules these screens have to carry

- Quitting applies the partial score **and −10, before the rank cap**.
- Fifteen seconds of grace from when the server declares the loss. Coming
  back inside it continues the original session.
- **Reloading the tab never resumes an attempt**, not even inside the grace
  window — and reloading is the reflex of someone who thinks the page froze.
- The current question's clock keeps running through a disconnection, and a
  sent question can time out without ever being displayed.
- No further question is sent until contact returns; questions never sent
  deduct nothing.
- A confirmed server-wide outage voids the attempt: zero adjustment, no quit
  penalty, no suspicious flag, no resume.
- **A failed request alone does not prove an outage.**

## Owner choices (2026-11-15)

| Question | Choice |
|---|---|
| The quit warning | The approved sentence, minimally corrected: the 10 points come off the result, rather than promising the balance will drop by 10 |
| The connection screen | A countdown bar plus the three things happening: the question clock is still running, reloading ends the attempt, and no new question arrives until contact returns |

Options not chosen: a quit warning showing the running arithmetic; a quit
warning with no figures at all; a bare countdown; and a countdown with the
consequences hidden behind a tap.

### Why the quit wording had to change

The decision record itself asks for this: the approved sentence promises
"you'll lose an additional 10 points", but the 10 are applied **before** the
cap. Near a cap they can vanish into the discarded overflow. Iron 990 with a
partial +100 computes 990 + 100 − 10 = 1,080 and caps to 1,000 — the balance
does not fall by 10, it rises. A player told they would lose 10 would see
1,000 and conclude the app lied.

The corrected sentence: "Quit this ranked quiz? Your current score will
count, and 10 points are taken off it. You cannot resume this attempt."
Only "off it" changed — the 10 come off the attempt's result, which is true
whatever the cap then does.

### Blame

**No screen says whose fault it was.** The app cannot tell a player's phone
from their signal from the warehouse wi-fi from its own server, so the
screens report what the server observed — "the server lost contact with this
quiz" — and nothing more.

## Screens

Added to `mockups/entry-navigation.html`. Fictional data; mock controls
switch between the states.

1. **Quit confirmation.** The corrected wording, the question clock still
   running, Continue quiz and Quit quiz.
2. **Quit finished.** Partial, −10, balance, and that the attempt is over.
3. **Quit near the cap.** The case that forced the rewrite: 990 + 100 − 10
   = 1,080, capped to 1,000, with both steps shown so the player can see why
   the balance did not drop.
4. **Connection lost.** The countdown and the three consequences.
5. **Reconnected in time.** The attempt carries on, with what is left of the
   current question's clock.
6. **Grace expired.** The partial score stands, **with no −10**, stated
   plainly so it is not mistaken for a quit.
7. **Server outage.** The attempt is voided: zero adjustment, no penalty, no
   flag. The only case where nothing counts.
8. **Page reloaded.** The attempt is over, and why reloading does not
   resume.

## Limits

- No screen assigns blame, promises a review, or offers an appeal. Opening a
  Support ticket stays the player's own choice, on the Support screen.
- No screen uses the word suspicious or anything like it. Connection
  instability flags exist, and they are never shown to a player as an
  accusation.
- Prize tie-breaks are slice 4.
- All scores and timings are invented.

## Checks

- **Readable labels.** Every outcome is named in words.
- **Phone layout.** 320 px and 375 px: nothing cut off, no sideways scroll.
- **Keyboard and focus.** Every control is reachable with Tab, works with
  Enter, and shows a visible focus outline. The quit confirmation returns
  focus to where it was opened from when dismissed.
- **Not colour alone.** Quit, expired, voided and reloaded are named in
  words.

## Recording the review

1. Show the owner each state in a browser at phone size.
2. Post one comment on #17 listing the approved states and the choices.
3. Boxes 3 and 4 are this slice's; tick them only once merged.

## Review record (2026-11-15)

The owner reviewed the states in a browser at 375 px, in two groups, and
approved them unchanged:

1. The quit confirmation and both quit results.
2. The five connection states: contact lost, back in time, grace expired,
   server outage, page reloaded.

Nine states were built rather than eight: a "back in the quiz" screen was
added so Continue quiz leads somewhere.

Wording settled while building:

- **The quit-near-cap screen shows both steps** — the 10 coming off, then
  the overflow discarded — under the heading "The 10 points came off, even
  though your balance went up". Without it, a player who quits at 990
  watches the balance rise to 1,000 and concludes the penalty was never
  charged, or that the app lied.
- **The outage screen says "a confirmed server problem"**, because a failed
  request alone does not prove an outage, and states that there is **no mark
  against the account** — the natural suspicion when a scored attempt is
  voided.
- **Grace expiry carries a "No extra penalty" block** saying in as many
  words that losing contact is not quitting.
- **Reconnecting says a question that ran out while contact was lost still
  counts as wrong**, because it does, and a player would not guess it.

### No route to Support from these screens

Deliberate, and confirmed on review. None of these outcomes changes points,
and a support button on the screen where a player feels robbed invites
tickets that can only be answered with "nothing can be changed". Opening a
ticket stays available on the Support screen in Profile.

Checked at 320 px and 375 px: all nine states render, no sideways scroll, no
JavaScript error.

## Delivery

Branch `codex/quit-connection-mockups` from `codex/ranked-mode`, opened as a
pull request for review.
