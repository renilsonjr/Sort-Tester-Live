# Profile mockups (Issue #16, slice 1)

First slice of #16. The entry and navigation mock (#15) left Profile as a
placeholder that only proved the path. This slice gives it its content: the
display identity, the single balance, the badge bands and the private
"pre season history" tab.

Issue #16 is split into five slices, each with its own mock, review and pull
request:

1. Profile (this slice).
2. Leaderboard.
3. Private settings: email and the launch reminder opt-in.
4. Account deletion.
5. Support tickets and retention states.

The sixth acceptance box of #16, the mobile/keyboard/loading/empty/error
review, is not a slice: each slice carries it.

This is a design for a mockup only. No app file (`index.html`, `src/`,
`backend/`) changes, and nothing here is a completed feature.

## Owner choices (2026-11-14)

Each choice was shown as three side-by-side phone sketches with fictional
data and picked one at a time.

| Question | Choice |
|---|---|
| Balance and badge bands | A balance card with a progress bar to the current badge cap, plus a "How badges work" row that opens the five-badge ladder |
| Profile structure | Three tabs: **Overview**, **pre season history**, **Settings** |
| Pre-Season history list | One list in date order with filters: All, Completed, Ended at launch. Each row carries a written status label |
| The history tab before launch | The tab is visible and holds a short notice; the list appears only after the official launch |

Options not chosen: a bare balance card, a permanently open badge ladder, two
tabs with everything in Overview, two tabs plus a separate account screen,
one history list without filters, two grouped history blocks, a live
Pre-Season list before launch, and a history tab hidden until launch.

The last choice is the one with no settled rule behind it. Decision 12 says
what the tab holds after the official launch and says nothing about before
it. The owner chose the option that adds no new rule: a notice, not a live
list. A live Pre-Season list would be more useful to players and remains
available as a later owner decision; it is not assumed here.

## Screens

Added to the existing `mockups/entry-navigation.html`, so the Profile tab
leads into them as it would in the app. Fictional data only.

1. **Overview.** Username, tag, the balance card, the "How badges work" row
   opening the ladder (Iron, Bronze, Silver, Gold, Challenger with their
   point bands and the current one marked), and the Support row.
2. **Overview, negative balance.** "Iron · −40 points" with an empty bar, to
   show the text carries the meaning on its own.
3. **Overview, at the badge cap.** At 1,000 points a promotion notice says a
   perfect 15/15 quiz is required and that **Start promotion** is on the
   Ranked screen. Profile announces promotion; it never starts one.
4. **pre season history, before launch.** The tab with the notice.
5. **pre season history, after launch.** The filtered list, each row showing
   the date, the result and a written status: Completed or Ended at launch.
   An attempt ended at launch shows no score and no invented answers.
6. **Settings.** The row names only: email and reminders, delete account,
   log out.

Also mocked, as #16 asks: the history tab **loading**, **empty** and
**error** states.

## Limits

- No official-season history screen: none is approved, and this slice does
  not invent one.
- Settings is a list of row names. Its content belongs to slices 3 and 4.
- The leaderboard is untouched; it is slice 2.
- No email address, ticket, connection detail or other player's data appears
  on any screen.
- "pre season history" is spelled exactly that way, as Decision 12 requires.
- The ladder shows the settled bands: Iron through 1,000, Bronze 1,001–2,000,
  Silver 2,001–3,000, Gold 3,001–4,000, Challenger 4,001 and up, uncapped.
- All usernames, tags, dates, scores and point totals are invented.

## Checks

- **Readable labels.** Every control has a text label; icons are decorative
  and hidden from screen readers.
- **Phone layout.** Checked at 320 px and 375 px, including whether the three
  tab names fit at 320 px. Nothing is cut off and nothing scrolls sideways.
- **Keyboard and focus.** Tabs, filters and the badge ladder are reachable
  with Tab, work with Enter, and show a visible focus outline.
- **Not colour alone.** Each history row names its status in words; the
  balance states the badge and point total in text, not only through the bar.

## Recording the review

1. Show the owner each screen in a browser at phone size.
2. Post one comment on #16 listing the approved screens and the choices.
3. Tick an acceptance box on #16 only when everything it asks for is done and
   merged. The first box (identity, balance, negative Iron, bands, promotion,
   the private history tab) is covered by this slice alone. The sixth box
   needs every slice, so it stays open until the last one merges.

## Delivery

Branch `codex/profile-mockups` from `codex/ranked-mode`, holding this
document and the mockup changes, opened as a pull request for review.
