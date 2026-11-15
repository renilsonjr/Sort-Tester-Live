# Ranked quiz mockups (Issue #17, slice 1)

First slice of #17, the last design issue. It covers the ordinary Ranked
quiz: the question, the feedback between questions, and the result.

#17 is split into four slices, each with its own mock, review and pull
request:

1. The ordinary Ranked quiz (this slice).
2. Promotion: the explicit start at a cap, and promotion results.
3. Quitting and losing connection.
4. Prize tie-break rounds.

The seventh acceptance box, the mobile, keyboard and readability review, is
not a slice: each slice carries it.

This is a design for a mockup only. No app file (`index.html`, `src/`,
`backend/`) changes, and nothing here is a completed feature.

## The rules these screens have to carry

- 15 questions, ten seconds each. **The clock belongs to the server**: it
  starts when the server sends the question, not when the browser shows it.
- An accepted answer is locked. A timeout counts as wrong.
- Per question: Easy +10 / −15, Medium +20 / −10, Hard +30 / −5. A whole
  ordinary quiz ranges from −150 to +300.
- Feedback stays on screen until the player presses Next; the next
  question's clock starts only after that. Repeated Next presses must not
  skip questions or create a second live question.
- **The final question settles the attempt without a Next**, and creates no
  extra question.
- One balance. Points above the badge cap are discarded, never banked.
  Iron 950 plus a raw +300 lands on 1,000, and 250 are gone.
- History keeps the raw result as well as the applied one.

## Owner choices (2026-11-15)

| Question | Choice |
|---|---|
| What the per-question feedback shows | The correction plus what the question was worth and its difficulty, for example "−10 points · Medium question" |
| How the result explains the cap | The arithmetic line by line — balance before, earned, what did not fit, balance now — plus the Start promotion action when the attempt ends at a cap |

Options not chosen: feedback with no points at all; feedback carrying a
running total; a result that only states the new balance; and a result that
compresses the arithmetic into one line.

**Why not a running total:** the only total available mid-attempt is the raw
one, and the cap is applied at the end. A player at 950 would watch "+300"
climb and finish at 1,000, with the app appearing to have taken 250 points.
The result screen is where that arithmetic can be shown honestly.

**Why the line-by-line result:** when the app takes something away, showing
the whole sum is what prevents the suspicion that it was taken quietly.

## Screens

Added to the existing `mockups/entry-navigation.html`, reached from Ranked.
Fictional data only; mock controls switch between the states.

1. **Question.** Counter, server clock, belt answers, Cancel.
2. **Answer locked.** Between the tap and the server's reply: no second
   answer, no changing the first.
3. **Feedback, right.** With "+20 points · Medium question" and Next.
4. **Feedback, wrong.** Choice, correct belt, the reason, and the deduction.
5. **Timed out.** Counts as wrong, said plainly so it does not read as a
   freeze.
6. **Final question.** Settles the attempt with no Next, which is the one
   exception to the other fourteen.
7. **Result at a cap.** The arithmetic line by line, then Start promotion.
8. **Result below a cap.** The ordinary case, with nothing discarded.
9. **Negative result.** A player who finishes down, stated without
   scolding them.

## Limits

- The clock shown is the server's. Nothing suggests reloading buys time.
- No promised response time, appeal route or support invitation on the
  result.
- Quitting, lost connection and tie-breaks belong to slices 3 and 4.
- Practice is untouched and still changes no Ranked points.
- All scores, codes and names are invented.

### Ranked and Practice look alike

The Ranked question screen and the Practice quiz that already exists are
nearly the same arrangement; the difference is that one costs points. The
mock marks the Ranked screens plainly, so nobody starts an attempt that
counts while believing it is practice.

## Checks

- **Readable labels.** Every state and control is named in words.
- **Phone layout.** 320 px and 375 px: nothing cut off, no sideways scroll,
  and the belt answers stay within thumb reach.
- **Keyboard and focus.** Answers, Next and Cancel are reachable with Tab,
  work with Enter, and show a visible focus outline.
- **Not colour alone.** Right, wrong and timed out are named in words; the
  belt colours stay as routing information.

## Recording the review

1. Show the owner each state in a browser at phone size.
2. Post one comment on #17 listing the approved states and the choices.
3. Box 2 (15 questions, ten seconds, locked answers, feedback until Next,
   the final answer settling on its own, raw versus applied results) is the
   one this slice can finish, and only its ordinary-Ranked half: its
   promotion half waits for slice 2. Box 1 is promotion entry, slice 2. Box
   7 waits for the last slice. Nothing is ticked until the work is merged.

## Delivery

Branch `codex/ranked-quiz-mockups` from `codex/ranked-mode`, opened as a
pull request for review.
