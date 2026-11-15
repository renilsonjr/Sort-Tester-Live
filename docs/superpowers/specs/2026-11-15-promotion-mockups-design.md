# Promotion mockups (Issue #17, slice 2)

Second slice of #17. Slice 1 covered the ordinary Ranked quiz; this one
covers promotion: the explicit start at a badge cap, the attempt itself, and
what happens when it succeeds, fails or a loss demotes the player.

Remaining after this: quitting and lost connection, then prize tie-breaks.

This is a design for a mockup only. No app file (`index.html`, `src/`,
`backend/`) changes, and nothing here is a completed feature.

## The rules these screens have to carry

From Decision 4 and the settled Q7:

- At a badge cap, **Start promotion is the only Ranked option**. Ordinary
  Ranked quizzes cannot start; Practice stays available.
- Promotion requires **15 of 15**. One wrong answer or timeout ends it.
- **A correct promotion answer adds nothing.** A wrong one deducts the usual
  amount for its difficulty.
- So a failed promotion drops the player below the cap: Iron 1,000 with one
  wrong Easy question becomes 985, and 15 points must be earned back in
  ordinary Ranked before promotion returns. History keeps the raw +275.
- Success sets the next cap plus one: Iron 1,000 becomes 1,001 and Bronze.
- **Opening the promotion information starts nothing** — not the attempt,
  not a question clock. Only the explicit action starts it.
- Losses demote: Bronze 1,010 with −150 becomes 860 and Iron. Regaining
  Bronze means reaching 1,000 again *and* passing another perfect
  promotion.
- Challenger is uncapped and has no promotion.

## Owner choices (2026-11-15)

| Question | Choice |
|---|---|
| How the cap screen offers promotion | Four numbered rules before the action: all fifteen needed, a wrong answer ends it and deducts, the deduction drops you below the cap, and success sets 1,001 and Bronze |
| What a failed promotion shows | The question that ended it, the arithmetic, and how many points are needed to reach the cap again |

Options not chosen: a single warning paragraph; the condition with the
consequence hidden behind a disclosure; the arithmetic without the question;
and the question without the distance back.

**Why all four rules up front:** this is the most expensive decision the app
offers a player. One wrong answer costs points *and* the chance to rank up.
Hiding "a wrong answer deducts" behind a tap hides exactly the part that
costs.

**Why all three parts of the failure screen:** a player who just failed has
three questions — what did I get wrong, what did it cost, and when can I try
again. Leaving any of them unanswered reads as the app withholding
something.

## Screens

Added to `mockups/entry-navigation.html`, reached from Ranked. Fictional
data; mock controls switch between the states.

1. **Ranked at the cap.** The balance at 1,000, the four numbered rules,
   Start promotion and Not now. No ordinary Ranked quiz is offered, because
   at the cap there is none.
2. **Promotion question.** The ordinary question screen, marked as
   promotion, showing the attempt is still perfect so far.
3. **Correct answer in promotion.** Which has to say something
   counter-intuitive: a correct answer adds nothing. It keeps the attempt
   alive, and the screen says that rather than showing "+0".
4. **Failed promotion.** The question that ended it, the arithmetic, and the
   distance back to the cap.
5. **Promotion passed.** 15 of 15: the new badge and the balance at cap plus
   one.
6. **Demotion.** A loss that drops a badge: Bronze 1,010 with −150 becomes
   860 and Iron, and regaining Bronze needs 1,000 again *and* another
   perfect promotion.

## Limits

- The information screen starts nothing. Only the explicit action does.
- No screen promises a date when promotion returns; it depends on the player
  earning the points back.
- Practice stays available at the cap, and the screens say so.
- Quitting and lost connection are slice 3.
- All scores, codes and names are invented.

### Two screens that need careful wording

**The correct answer in promotion.** "You were right, and gained nothing"
reads like a bug. The screen says what the correct answer actually buys —
staying in the attempt — instead of displaying a zero.

**The demotion.** It is the only screen where a player loses a badge they
already held. It states the arithmetic and what regaining the badge takes,
without dressing the loss up.

## Checks

- **Readable labels.** Every state and control is named in words.
- **Phone layout.** 320 px and 375 px: nothing cut off, no sideways scroll.
- **Keyboard and focus.** Every control is reachable with Tab, works with
  Enter, and shows a visible focus outline.
- **Not colour alone.** Passed, failed and demoted are named in words.

## Recording the review

1. Show the owner each state in a browser at phone size.
2. Post one comment on #17 listing the approved states and the choices.
3. With this slice merged, boxes 1 and 2 are both covered — box 1 entirely,
   box 2 completed by its promotion half, which slice 1 left open.

## Review record (2026-11-15)

The owner reviewed the states in a browser at 375 px, in two groups, and
approved them unchanged:

1. The cap offer and the promotion question.
2. The correct answer, the failed promotion, the passed promotion and the
   demotion.

Wording settled while building:

- **The correct answer never shows "+0".** It reads "Correct · still
  perfect", says how many are right so far and how many remain, and
  explains that a right answer keeps the attempt alive rather than adding
  points.
- **The failed promotion names the raw total too**, so a player can see
  that the +275 they earned is kept in history even though −15 was applied.
- **The demotion states both conditions** for getting the badge back:
  reaching 1,000 again *and* passing another perfect promotion.
- The cap screen says in as many words that opening it has started nothing,
  because the rule requires it and because otherwise a player hesitates to
  look.

### A fix this slice forced

The app settled on 2026-11-14 that quiz screens use a brown primary so that
yellow only ever means a belt. The mock had kept gold on those screens,
which contradicted the app exactly where GOLD and YELLOW chips appear — the
failed promotion shows a GOLD chip. The mock now carries the same rule and
the same comment.

Applying it exposed a missing `--accent-ink` token in the mock: the button
label turned dark-on-dark and vanished. Found by looking at the screen after
the change, not by the tests.

Checked at 320 px and 375 px: all six states render, reopening always lands
on the offer rather than mid-attempt, no sideways scroll, no broken image,
no JavaScript error.

## Delivery

Branch `codex/promotion-mockups` from `codex/ranked-mode`, opened as a pull
request for review.
