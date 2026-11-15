# Prize tie-break mockups (Issue #17, slice 4)

Last slice of #17, and the last mockup work on this project. It covers the
separate quizzes that settle a tie for one of the three prize places.

This is a design for a mockup only. No app file (`index.html`, `src/`,
`backend/`) changes, and nothing here is a completed feature.

## What makes these screens unlike every other screen

**They withhold information on purpose.** A player answers five questions
and is shown nothing: not whether they were right, not a score, not the
correct answer, until the round's 24-hour window closes. Every other screen
in this app reports immediately.

So these screens have two jobs at once: keep the secret, and not look
broken. A blank result reads as a bug or as favouritism unless the screen
says plainly that it is hidden for everyone, and why.

## The rules these screens have to carry

- Five shared Hard work-methods questions per round, the same for everyone
  in it. Correct +1, wrong or timed out 0, so 0 to 5. **No seasonal points
  change.**
- Questions advance by themselves. **There is no Next button**, and no
  feedback pause between them.
- Timers shorten: five seconds for Challenger and lower-rank rounds 1 to 3,
  four seconds in round 4, three in round 5.
- Played asynchronously, once per participant per round, inside a 24-hour
  window. The first deadline is scheduled season close plus 24 hours.
- Nothing is revealed until that window closes — not scores, not
  correctness, not the answers.
- Challenger allows at most three valid rounds; lower ranks at most five.
  After that, a remaining tie waits for **owner selection**.
- If there is no fresh set of five approved Hard questions, the round does
  not run and that place waits for owner selection too. **Questions are
  never silently reused.**
- A completed attempt outranks an incomplete one or a no-show. At the close
  of a valid Challenger round, a participant who did not complete is
  excluded from the top three; if both fail to complete, both are.
- Exclusion affects prize placement only: points, badge and history are
  untouched.
- A confirmed outage restarts the whole round for everyone, including
  players who already finished, with fresh questions and a new window. It
  does not consume a round from the limit.

## Owner choices (2026-11-15)

| Question | Choice |
|---|---|
| The submitted screen | Both: what was recorded for each of the five, without saying whether any was right, **and** why nothing is shown yet |
| The question timer | A bar that empties just above the question, rather than a numeric clock |

Options not chosen: a submitted screen with only the reassurance; one with
only the explanation; a round clock like the ordinary quiz's; and a clock
with five progress dots.

**Why both halves of the submitted screen:** a player who has just answered
five questions in three seconds each has two fears in order — "did my
answers arrive?" and "why won't they tell me anything?". Showing what was
recorded answers the first; explaining the shared questions answers the
second. Secrecy without a reason reads as favouritism.

**Why a bar and not a clock:** at three seconds, looking away from the
question to read a number costs the answer. A bar shortening just above the
question is noticed without being read.

## Screens

Added to `mockups/entry-navigation.html`. Fictional data; mock controls
switch between the states.

1. **Round invitation.** The tie, five Hard questions, the per-question
   time for this round, the 24-hour window, and that it can be played at any
   point inside it. An explicit Start round; nothing begins before it.
2. **Question.** The emptying bar, the position in the five, and the notice
   that there is no Next.
3. **Submitted.** What was recorded for each of the five, and why nothing is
   shown yet.
4. **Round result.** After the window: each participant's 0 to 5, and
   whether the place is settled.
5. **Still tied.** A fresh round opens, with new questions and a new
   24-hour window.
6. **Did not complete.** Excluded from the top three, with points, badge
   and history explicitly unchanged. For Challenger, both players can be
   excluded.
7. **Rounds exhausted.** After the limit, the place waits for owner
   selection.
8. **No questions available.** No fresh approved set, so the round does not
   run and the place waits for owner selection.
9. **Outage during a round.** The whole round restarts for everyone,
   including players who had finished, and does not consume a round.

## Limits

- **No leak before the deadline**: no screen shows correctness, a score, a
  correct answer, or another player's result.
- Every state repeats that this changes **no points and no badge**. The
  quiz feels like it decides everything, and in points it decides nothing.
- No invented order between tied players, in any state.
- Nothing about who answered first.
- All names, dates and scores are invented.

### Screens 7 and 8 need care

Both hand the decision to the owner. Said badly, that reads as the app
giving up, or as favouritism. They state that it is a rule agreed in
advance, name the limit that was reached, and say what is preserved: points,
badge, history, and the relative order already earned in valid rounds.

## Checks

- **Readable labels.** Every state and outcome is named in words.
- **Phone layout.** 320 px and 375 px: nothing cut off, no sideways scroll,
  and the answer choices stay reachable within the short timer.
- **Keyboard and focus.** Every control is reachable with Tab, works with
  Enter, and shows a visible focus outline.
- **Not colour alone.** Settled, still tied, excluded and voided are named
  in words.

## Recording the review

1. Show the owner each state in a browser at phone size.
2. Post one comment on #17 listing the approved states and the choices.
3. Boxes 5 and 6 are this slice's. **Box 7 closes with it too**, being the
   mobile, keyboard and readability review across all four slices — this is
   the last one, so #17 can close when this merges.

## Delivery

Branch `codex/tiebreak-mockups` from `codex/ranked-mode`, opened as a pull
request for review.
