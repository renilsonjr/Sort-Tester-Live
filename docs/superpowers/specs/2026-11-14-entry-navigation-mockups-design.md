# Entry and navigation mockups (Issue #15)

Issue #15 asks for reviewed mockups of the public entry and the navigation
between modes before any new screen is built. This document records the three
visual choices the owner made on 2026-11-14 and what the mockup will contain.

It is a design for a mockup only. No app file (`index.html`, `src/`) changes,
and nothing here is a completed feature.

## Owner choices (2026-11-14)

Each choice was shown as three side-by-side phone sketches with fictional data
and picked one at a time.

| Question | Choice |
|---|---|
| Visual base | The live app's current style in `index.html` (Nunito, rounded cards, indigo accent, bottom tab bar) |
| Public entry | Two explained cards: a Ranked card with **Log in** and a Practice card with **Continue as guest**, under the sort-change announcement |
| Guest navigation | Two tabs, **Home** and **Practice**, with a small **Log in** button in the header |
| Logged-in navigation | Four tabs: **Home**, **Practice**, **Ranked**, **Profile**. Leaderboard lives inside Ranked; Support → Tickets lives inside Profile |

Consequence of the tab choices: today's separate Study and Quiz tabs become
one **Practice** tab holding both.

Options not chosen: a five-tab bar, an account menu in the header, a plain
two-button entry, entering straight into guest mode, locked Ranked/Profile
tabs for guests, and a "Log in" tab.

## Screens

One self-contained file, `mockups/entry-navigation.html`, clickable, with
fictional data, in the same manner as `mockups/friendly-study.html`.

**Before login**

1. **Entry.** Sort-change announcement first, then the Ranked card with
   Log in, then the Practice card with Continue as guest. No tab bar yet.
2. **Log in.** One field, the login ID, plus Create account. This matches the
   existing sign-in.
3. **Lost login ID.** Text only: ask the owner in person at work. No form and
   no email field, because only the admin can restore access after in-person
   verification (Decision 14).

**Guest (two tabs)**

4. **Guest home.** Announcements, shortcuts to study and quiz, Log in in the
   header.
5. **Practice.** The two existing choices, "Know the chart" and "Try a quiz".
   Same screen for guests and logged-in players.

**Logged in (four tabs)**

6. **Home.** The same sort-change announcements.
7. **Ranked.** Season status, a start action, and the way into the
   leaderboard.
8. **Leaderboard.** Reached from Ranked.
9. **Profile.** Fictional username and tag, a Support row and Log out.
   Support opens **Tickets** with a Create ticket button.

## Limits

- Ranked, Leaderboard, Profile and Tickets are thin placeholders that only
  prove the path. Their content belongs to #16 and #17 and is not decided
  here.
- No guest screen shows any player data: no usernames, tags, scores, history
  or contact details. Leaderboard is reachable only after login.
- Support contains Tickets and nothing else. Create ticket is a button with
  no form behind it (#26 owns that).
- Tickets, email and recovery details never appear on Profile or Leaderboard
  placeholders.
- The language switch in the header stays where it is today.
- All names, tags, ZIP codes and numbers are invented.

## Checks

- **Readable labels.** Every button and tab has a text label; icons are
  decorative and hidden from screen readers.
- **Phone layout.** Checked at 320 px and 375 px wide: nothing is cut off and
  nothing scrolls sideways.
- **Keyboard and focus.** Every control is reachable with Tab and works with
  Enter, with a visible focus outline.
- **Not colour alone.** The active tab carries `aria-current="page"` as well
  as its colour. The sort-change announcement names the belt in words.

## Recording the review

1. Open the mockup in a browser at phone size and show the owner each screen.
2. Post one comment on #15 listing the approved screens and the choices in
   the table above.
3. Tick an acceptance box on #15 only when everything it asks for is done and
   merged.

## Delivery

Branch `codex/entry-navigation-mockups` from `codex/ranked-mode`, holding this
document and the mockup file, opened as a pull request for review.
