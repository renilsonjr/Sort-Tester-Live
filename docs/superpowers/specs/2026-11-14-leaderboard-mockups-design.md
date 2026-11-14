# Leaderboard mockups (Issue #16, slice 2)

Second slice of #16. Slice 1 gave Profile its content; the leaderboard is
still the three-row placeholder that #15 left behind. This slice gives it
the eligibility rule, the provisional states and the notices that go with
them.

Remaining slices after this one: account deletion, and Support tickets with
their retention states. The private-settings slice was folded away when the
owner withdrew email on 2026-11-14; what survived of it is the home-page
launch callout, already built, and the privacy rule that every slice carries.

This is a design for a mockup only. No app file (`index.html`, `src/`,
`backend/`) changes, and nothing here is a completed feature.

## Owner choices (2026-11-14)

Each choice was shown as three side-by-side phone sketches with fictional
data and picked one at a time.

| Question | Choice |
|---|---|
| A player with no competition position | The standings first, then a block at the end naming the reason and pointing the player at the owner |
| Telling the player the result is not final | A short notice above the list, plus a written marker on each affected row |

Options not chosen: a balance card above the list, a pinned footer row with a
dash for the position, a notice with no row markers, and a "Provisional" chip
on the title with no notice.

## Screens

Added to the existing `mockups/entry-navigation.html`, reached from Ranked,
as #15 settled. Fictional data only. Mock controls switch between the states.

1. **During the season.** Position, username, tag, badge and points, with the
   player's own row marked. A short line saying the standings update after
   each settled Ranked quiz, not on a daily schedule.
2. **No competition position.** The same standings, then the end block: the
   player's own points and badge still count, the competition is for Primary
   Sort on Twilight approved by the owner, and asking the owner is the next
   step.
3. **Provisional with a tie.** The notice above the list; both tied players
   shown at the same position, each row carrying "Tied for third · tie-break
   quiz pending".
4. **Provisional after a replacement.** A place vacated by a withdrawal or an
   uncompleted tie-break is filled from the next eligible player; the notice
   says a place was filled and that this can create a new tie.
5. **Final.** No provisional notice; the three prize winners marked as such.
6. **Fewer than three winners.** Prize places left vacant because no eligible
   player fills them, stated plainly, with no invented third name.
7. **Loading, empty and error.** Empty is the start of a season, before
   anyone has completed a Ranked quiz.

## Limits

- **No timestamps of any kind**, and nothing about who reached a score first.
  The first-reached-score rule was superseded; showing a time would quietly
  bring it back.
- No real name, employee ID, email, ticket or connection detail. Public
  identity is username, tag, badge and points.
- The screens never show who the owner approved and who they did not. A
  player without a position sees only their own situation.
- No invented order between tied players, and no extra tie-break to separate
  places below the top three.
- The leaderboard still requires login; guests keep Practice and study.
- Ranked quiz screens, promotion and tie-break play are #17 and #24, not this
  slice.
- All usernames, tags, points and positions are invented.

## Checks

- **Readable labels.** Every control and every state has a text label.
- **Phone layout.** Checked at 320 px and 375 px: nothing cut off, no
  sideways scroll, and long usernames do not push the points off the row.
- **Keyboard and focus.** Mock controls and any row action are reachable with
  Tab, work with Enter, and show a visible focus outline.
- **Not colour alone.** A tied row, a replaced place and a winner each say so
  in words; the tinted background is secondary. The player's own row is
  marked in text as well as by its border.

## Recording the review

1. Show the owner each state in a browser at phone size.
2. Post one comment on #16 listing the approved states and the choices.
3. Tick box 2 only once this slice is merged. Box 6 waits for the last slice.

## Delivery

Branch `codex/leaderboard-mockups` from `codex/ranked-mode`, holding this
document and the mockup changes, opened as a pull request for review.
