# Handler — conveyor mini-game rules and delivery stages

Player-facing name: **Handler**. Internal name and issue titles: conveyor.

**Status:** Design approved by the owner on November 24, 2026. The issues were rewritten from it on November 26, 2026, and stage 1 is built. Stages 2 to 6 are not started.

Parent tracker: issue #392. Sub-issues #393, #394, #395, #396, #397. This document supersedes the "choices still to make" list in #392 for the three areas the owner settled on November 24, 2026 (round end, difficulty modes, score persistence); every other caveat in #392 still stands.

## What changed on November 24, 2026

#392 captured the game concept but left the product rules open, and its sub-issues were written for a Practice-only feature that saved nothing and touched no backend. The owner settled the open rules and, in doing so, changed that boundary: the first release now saves a best score per mode, which is new stored data. A mini-game leaderboard is wanted but is deliberately deferred to a sixth stage so the game can reach a phone first. That privacy decision was made on November 26, 2026 and is recorded under stage 6.

## Game rules

Rules 1–11 restate the concept agreed in #392. Rules 12–21 are the owner's November 24 decisions. Rules 22 to 25 are his November 26 decisions: the label, the skin, the gesture and the sound.

**The belt**

1. Packages enter at the top and travel down toward the player. Following packages stay visible in the queue behind the front one.
2. Only the front package can be sorted.
3. The label shows the routing code **and the service**, because routing depends on both. Never fabricate a five-digit ZIP from a prefix or preload code.

Settled on November 26, 2026 (rule 22 below): the label shows **one concrete code**, never a chart range.

**The choice**

4. Each active package offers exactly two destinations: one correct belt and one wrong belt. Each shows the belt color and its written name.
5. The correct destination comes from the route rules and is never randomized. Only the left/right position is randomized.
6. The wrong destination is a valid belt, different from the correct one.
7. Options stay fixed until the front package is resolved. A following package cannot change the active package's answer, and a late gesture for an already-resolved package is ignored.

**The three outcomes**

8. **Sort** — swiped to the correct belt.
9. **Missort** — swiped to the wrong belt.
10. **Drop** — the package passes the bottom edge without being sorted.
11. The three outcomes are counted separately and each package resolves exactly once.

**Round and scoring**

12. A round lasts **two minutes**. It ends when the clock reaches zero, not when packages run out.
13. A sort scores **1 point multiplied by the current combo multiplier**.
14. A missort **subtracts 1 point** and resets the combo to zero.
15. A drop **subtracts 1 point** and resets the combo to zero.
16. The **combo** is the number of consecutive sorts. The multiplier is x1 at 0–4, x2 at 5–9, x3 at 10–14 and x4 at 15 or more. x4 is the ceiling.
17. The score never falls below zero.
18. The end-of-round summary shows points, sorts, missorts, drops, accuracy and the round's highest combo.
19. The combo is shown two ways while playing, and both are owner-requested: a **ring of sparkles around the front package**, growing in number and brightness as the streak holds, and a **floating cartoon badge at the top right of the stage** carrying the multiplier, which is absent below x2, appears when the first tier is reached, brightens with each tier, and lifts away when the combo breaks. Breaking a combo scatters the sparkles rather than fading them. Nothing else on the screen reacts: the belt stays the belt. The owner rejected an earlier version where the package and the belt caught fire — the effect is a sparkle, not a flame.

The badge is off to the right and never over the lane. The owner found a centred badge covering the code on the package coming down, and reading that code early is the whole skill the game trains. Nothing may be placed over the lane above the front package for the same reason.

The sparkle is an icy cyan, chosen to sit far from the BLUE belt's navy so a glow around a package can never be mistaken for a routing color; belt names remain the only place a color means a destination. Motion is never the only channel: the tier is carried by the badge's color and by the written multiplier and streak count, so the information survives `prefers-reduced-motion`, which stills the twinkle and the lift.

20. The outcome is said **on the package itself**: it washes green with a tick on a sort, red with a cross on a missort or a drop, holds for a beat where it was, then leaves the belt. The colour and the glyph always travel together, because red and green alone fail red-green colour blindness. There is **no running commentary under the belt**; the owner found that text pulled the eye off the lane, and the screen it used now belongs to the game. The outcome still goes to a visually hidden live region for screen readers.
21. The game has **sound**: an arcade loop, the belt's own running noise whose pitch follows the live belt speed, and one cue each for a sort, a missort, a drop and **reaching a combo tier**. A drop sounds like a thud rather than like a wrong answer, because they are different mistakes. The tier cue is a rising arpeggio, longer and higher at each step, and it plays inside the badge's bump so the sound and the movement are one event. The belt's own noise stays quiet — it is the room, not an instrument, and the sort and missort cues have to cut through it. A **sound toggle** is always visible and its setting is remembered; audio starts only after the player starts a round, never on page load. The game must be fully playable with the sound off, which rule 20 guarantees.

22. The label shows **one code, never a range**. A chart main row is written as a range of three-digit prefixes because that is the shape of a chart row; a package in the hub carries one code. So the adapter **draws one prefix out of the range**, which is what a handler reads off a label. Two things keep the draw honest:

- A prefix that any exception row of the same service touches is **removed from the draw**. `TN|370–385` is BROWN but `TN|376–378` is BLUE, so 376, 377 and 378 never come out of the BROWN row. `NE|575 3-6` is ORANGE inside a BROWN range, so 575 is removed as well: its answer turns on a fourth digit the label would not show, which makes a bare `575` a question with no right answer. Those prefixes are not lost, because the exception rows carry them with the fourth digit visible.
- The removed set is **computed from the chart, never typed by hand**, so correcting the chart recomputes it. A test asserts the computed set equals the `exclusion_refs` the owner reviewed in `backend/data/ranked/routes-v1.json`, in both directions, so correcting one side and forgetting the other fails the suite instead of teaching a player the wrong belt.

A full five-digit ZIP was asked for and is **not possible from repository data**: neither the chart, the Ranked bank nor the player manual holds a ZIP list, and the chart routes by prefix. The owner declined adding an external ZIP dataset on November 26, 2026, so the label stops at the prefix, or at the prefix and fourth digit where the chart writes one. Do not reintroduce a generated five-digit ZIP as an improvement; rule 3 forbids it.

23. **Handler has a skin of its own and stays dark in both app themes.** It is a game inside the app, not another app screen, and the look is the one the owner approved on the prototype: a conveyor with a frame, running slats, dashed guides and a toothed end bar; packages that are taped boxes carrying a shipping label with the service, the routing code, the state and a barcode; the two destinations as tabs on the belt's own edges rather than buttons under the stage; and a three-cell strip for score, time left and the sorted / wrong / dropped tally.

The first build of the screen used the app's tokens instead, and the owner rejected it on November 26, 2026. The instruction in #395 that the prototype is "a reference for the feel, not code to copy" means do not paste its HTML. It does not mean discard the design, which the owner had already approved in these words: "o prototipo que vc fez esta otimo". The skin declares its own tokens on `.hd` and in `SKIN` in `src/conveyor/view.js`; nothing in that block follows `html[data-theme="day"]`.

The belt is narrow and centred, which is what makes room for the side destinations and the combo badge at once. `stageLayout()` reserves the badge's column and lets the belt give up width first on a narrow phone, so rule 19 holds by geometry at every width rather than by eye.

Two points where Handler deliberately departs from the prototype, both recorded so they are not "fixed" back:

- The prototype sets the badge's multiplier and streak line **side by side**, which makes the badge wide enough to sit over the belt again. Handler stacks them, which keeps the badge and rule 19 at the same time.
- The prototype twinkles the top tier **for ever**. This app allows no infinite animation anywhere in `index.html`, and `tests/promotion-celebration.test.mjs` asserts it for the whole page, so Handler twinkles three times and rests.

24. **The front package follows the finger.** A drag starts only when the finger lands on that box; anywhere else on the stage is a scroll. The box moves and leans under the thumb rather than waiting for the gesture to end, and a drag shorter than the swipe threshold is a change of mind that resolves nothing. A resolved package holds where it was wearing its verdict, then leaves towards the belt it was sent to; a dropped one falls straight past the end instead, because that is a different mistake. Losing a streak scatters the sparkle ring outward rather than switching it off.

25. **The sound levels are the owner's.** `src/conveyor/audio.js` is a port of the prototype's synthesiser, down to the master and music bus levels and the note choices for each cue. An earlier pass invented them and came out two to three times too quiet, so the game sounded as though it had no sound at all; the owner confirmed it audible on November 26, 2026. A test pins the numbers, so retuning has to be deliberate. #397 is where the owner tunes them after playing.

The owner's reason for rules 14 and 15: a missort has a real cost in the hub, because the package goes to the wrong place and comes back. The x4 ceiling in rule 16 is an assistant proposal chosen without measurement; it is expected to be tuned in stage 5 after the owner plays, so it must live in a single named constant.

## Modes

The player chooses a mode before the round starts. Easy, Medium and Hard reuse the existing `LEVEL_DECKS` in `src/levels.js` rather than classifying routing content again.

| Mode | Speed | Routing content |
|---|---|---|
| Easy | slow | Basic deck |
| Medium | normal | Medium deck |
| Hard | fast | Hard deck |
| Expert | starts fast and keeps accelerating | starts Medium, ends on Hard |

Expert is not an easier ramp: it opens at Hard's pace and climbs from there, and its routing content hardens as it goes. Each mode keeps its **own best score**. Scores from different modes are never compared, merged or summed, because a two-minute timed round makes them incomparable. Expert needs two rules that no other mode needs: how the speed climbs, and when the deck changes. Both are decided in stage 1 and tested in stage 2. The prototype currently runs Expert from 84 to 132, with the deck changing a third of the way in; those are starting points for stage 5 to tune, not measured values.

## Where it lives in the app

Verified against `origin/main` at commit `178d940` on November 24, 2026.

The mini-game gets **its own tab in the bottom dock and its own stripe on Home**, which is how Practice already works — a tab in `navTabs()` plus a shortcut on Home. It is not a sub-screen of Practice and not a mode inside the quiz.

**Name.** The game is called **Handler**, after the job title. That is the name the player sees: the tab label, the Home stripe and the end-of-round screen. The internal name stays "conveyor" — the issue titles, the module folder `src/conveyor/` and this document — so the existing issues do not have to be renamed. Keep the two apart deliberately; do not rename one to match the other.

**Bottom dock.** Add a fifth entry to `navTabs()` in `src/app.js`, labelled "Handler". The dock today holds Home and Practice for a guest, plus Ranked and Profile once signed in, and its columns are an even `repeat(n, 1fr)` split. A fifth tab leaves roughly 75px per tab on an iPhone. "Handler" is seven characters and is a job title, so it stays "Handler" in Spanish as well; it still needs an entry in `src/i18n.js`, because every displayed string goes through `t()`. Measure the dock at phone width before accepting the label; do not eyeball it.

**Home.** A stripe of its own, placed after the Ranked hero stripe (the one titled "Play for the podium") and before the Practice stripe. The owner asked for it directly below the podium. It carries the game's name, one line saying what it is, and a button that starts mode selection. It does not go inside the Ranked stripe: the persistence boundary below keeps the mini-game out of Ranked, and sharing that stripe would say the opposite.

**Guests.** A guest can play, the same way a guest can practise. The best score is saved only for a signed-in account, and the end-of-round screen says so instead of hiding the result. Nothing about the game is gated behind signing in.

Both changes land in stage 3 for the screens and stage 4 for the navigation wiring.

## Persistence boundary for the first release

The first release stores exactly one thing: the best score for each of the four modes, per account. Nothing else. Mini-game results never reach Ranked points, prizes, badges, the leaderboard or the Shift log. A new table requires a GRANT to the app role before the image is swapped, or the app starts broken.

## Delivery stages

The dependency order from #392 is unchanged: data, then logic, then screen, then integration, then release. What changes is the content of four issues, plus one new stage.

**Stage 1 — #393 · routing data and modes. Built on November 26, 2026.** The four modes are wired to the existing level decks, the adapter draws a card and assembles the two-option pair, and the Expert acceleration and deck-change rules are decided: Expert opens at Hard's speed and climbs by half again over the round, with the deck hardening one third of the way in. Every tuning number sits in `MODES` in one place, for #397 to change after the owner plays. The stage touches no DOM, no canvas, no audio and no storage.

**Stage 2 — #394 · game engine.** Adds the two-minute clock, the combo and multiplier, the zero floor and the Expert acceleration curve to the existing acceptance list. All of it is browser-independent logic, testable with a fake clock and an injected random source. Rules 1–25 become tests here. **Issue text needs the new rules added.**

**Stage 3 — #395 · screen and input. Built on November 26, 2026 (PR #483).** Adds three screens the prototype does not have: mode selection, a visible countdown, and the end-of-round summary from rule 18. Build the rule 19 sparkle ring and cartoon combo badge, the rule 20 verdict on the package, and the rule 21 sound and its toggle here. Also build the Home stripe described above. **Issue text needs the new screens added.**

**Stage 4 — #396 · integration into Practice. Built on November 26, 2026 (PR #484).** Its current text forbids new stored data, which now conflicts with the approved best-score rule. Replace the prohibition with the persistence boundary above, including the table and its GRANT. This stage also adds the fifth tab to `navTabs()` and wires it, with the dock measured at phone width. Mounting and unmounting must clear the animation frame, the round clock and the pointer and keyboard listeners, so re-entering the tab cannot leave two belts or two clocks running. **Issue text needs rewriting.**

**Stage 5 — #397 · iPhone validation and release.** Mostly unchanged. Add two checks: reconcile the clock, score, combo and the three counters against a controlled two-minute run, and confirm the Escalation curve stays playable on a phone. Tune the rule 16 ceiling here, after the owner plays.

**Stage 6 — #417 · mini-game leaderboard.** A leaderboard of its own, separate from Ranked, split by mode. The owner decisions that had to come before any code were made on November 26, 2026:

- **Handler is a mini-game, not practice.** Earlier text in #417 called it practice; that framing is withdrawn.
- **Identity: the same as the Ranked leaderboard.** A row shows the account's username and tag and the icon the player chose, exactly what `backend/ranked/standings.py` exposes, and nothing more. No real-name field, no chosen alias of its own, no initials.
- **No opt-out.** Every signed-in player with a best score in a mode is on that mode's board.
- **Guests never appear.** A guest's score is still not stored anywhere.
- **Lifetime and deletion follow Ranked.** A deleted account is not listed (`deleted_at IS NULL`, as on the Ranked board), and its stored scores go with the account. Like the Ranked board, it is visible only to signed-in players.

Two things do not carry over from Ranked, because they are about the prize: there is no owner approval step (`participant_links`) and no minimum of one completed Ranked quiz. Scores are never compared across modes (rule 16), and nothing from this board feeds Ranked points, prizes, badges or the Shift log.

- **The board starts over each season.** It follows the Ranked season: when a new season begins, every mode's board is empty again. The stage 4 table keeps one all-time best per account and mode, so this needs the score stored per season, which is a schema change with its own GRANT.
- **The personal best starts over with it.** The best score a player sees on the mode screen is the best of the current season, the same number the board shows. There is no separate all-time best.

## Prototype status

A playable prototype exists as a private artifact, updated November 24, 2026 to follow rules 12–21: the two-minute clock, mode selection for all four modes, the sparkle ring and the cartoon combo badge, the green and red verdict on the package, the synthesized arcade sound, the end-of-round summary, and a best score per mode kept in browser storage. Its scoring was checked against four sample sequences (twelve straight sorts scoring 1/1/1/1/1/2/2/2/2/2/3/3, a missort dropping the total by one and clearing the combo, the zero floor holding, and the multiplier stopping at x4). It was not measured on a phone; stage 5 does that.

The prototype's routing content is generated from the app's own `LEVEL_DECKS` on `origin/main` at `178d940` — 26 Basic, 186 Medium and 280 Hard cards — using the real `BELT_STYLE` colors. The decks are read straight from the chart, so this is the app's current routing content, but the owner has not re-approved it for a game and the `CHECK` belt is excluded by the deck filter.

**That finding is now closed.** 367 of those 492 cards carried a *range* as their code, such as `010–024`, because that is the shape of a chart row. Rule 22 settles it: the adapter draws one prefix out of the range and removes the prefixes any exception of the same service touches. Measured across the chart, that is 26 prefix-and-service pairs, and the reviewed Ranked bank marks the same 26 through its `exclusion_refs`.

Stage 1 is built in `src/conveyor/routes.js`, tested in `tests/conveyor-routes.test.mjs`. What the modes now offer, measured rather than estimated:

| Mode | Deck cards | Distinct labels |
|---|---|---|
| Easy | 26 | 332 |
| Medium | 186 | 3,809 |
| Hard | 279 | 3,902 |
| Expert | 465 | 3,902 |

The prototype in `mockups/handler-prototype.html` still shows ranges. It was not updated, and it is not the specification; where the two disagree, this document and `src/conveyor/routes.js` win.

## Stage 5 findings, before the owner plays

Measured on November 26, 2026. None of this replaces the owner playing on an iPhone, which is what #397 is for; it is what could be established without one, so that session starts from numbers rather than from a blank page.

**The round reconciles.** `tests/conveyor-reconcile.test.mjs` plays a full two-minute round in every mode with a deterministic player, records every sort, missort and drop, and recomputes the score, the streak and the three counters independently from rules 13 to 17. The engine and the recomputation agree at every event in all four modes, including a round driven to zero and held there.

**The routing content holds.** All 491 cards and 8,043 labels offer one correct belt and only real wrong ones, each checked against the chart row it came from. Over 20,000 draws the correct belt was on the left 49.9% of the time.

**What each combo tier costs.** `node tools/handler-tiers.mjs` prints this; run it again after changing a constant.

| Mode | Packages in a round | Wrong 1 in 25 | Wrong 1 in 15 | Wrong 1 in 10 | Wrong 1 in 7 |
|---|---|---|---|---|---|
| Easy | 26 | x4, 66 points | x3, 44 | x2, 31 | x2, 23 |
| Medium | 38 | x4, 89 | x3, 63 | x2, 47 | x2, 33 |
| Hard | 53 | x4, 133 | x3, 89 | x2, 63 | x2, 46 |
| Expert | 69 | x4, 176 | x3, 117 | x2, 85 | x2, 61 |

Two things in that table answer #397's question, and one of them runs against intuition:

- **x4 asks for roughly one mistake in twenty or better.** A player wrong one time in ten never leaves x2, in any mode.
- **x4 is hardest to reach in Easy, not easiest.** It needs 15 straight, and an Easy round holds only 26 packages, so the streak is more than half the round. Expert holds 69. The slow belt gives more time per package and fewer chances to build the streak.

Whether that is right is the owner's call. The knobs, each a single named constant:

| What it changes | Constant | File | Now |
|---|---|---|---|
| Sorts per multiplier step | `COMBO_STEP` | `src/conveyor/engine.js` | 5 |
| Highest multiplier | `COMBO_CAP` | `src/conveyor/engine.js` | 4 |
| Round length | `ROUND_MS` | `src/conveyor/engine.js` | 120000 |
| Packages in sight | `PACKAGE_GAP_RATIO` | `src/conveyor/engine.js` | 1/3 of the lane |
| Belt speed per mode | `MODES` | `src/conveyor/routes.js` | 42 / 60 / 84 / 84 to 132 px/s |
| When Expert's deck hardens | `EXPERT_DECK_SWITCH` | `src/conveyor/routes.js` | 1/3 of the round |
| Swipe distance | `SWIPE_MIN` | `src/conveyor/view.js` | 52px |
| Sound levels | `MASTER_GAIN`, `MUSIC_GAIN`, `BELT_GAIN` | `src/conveyor/audio.js` | 0.85 / 0.15 / 0.035 |

They stay in the module that uses them rather than in one shared file, because `engine.js` imports nothing by design and a test holds it to that.

**Expert at the end of the round.** The belt reaches 132 px/s: a package crosses the lane in 4.2 seconds and a new one arrives every 1.4. Whether that is playable is a question for a thumb on a phone, not for a table.

**The verdict under colour blindness.** The distance between the green and the red, in RGB, is 206 for typical vision, 110 under simulated protanopia and **43 under simulated deuteranopia**, where the two are close to one colour. The tick and the cross are therefore the only channel that survives, which is why rule 20 requires them and a test holds them in place.

**Frame time.** With three packages on the belt, the multiplier at x4 and the sparkle ring at its densest, on Expert at 113 px/s: median 16.7 ms, 95th percentile 17.5 ms, worst frame 17.6 ms over 60 frames. That is desktop Chrome drawing a 670 by 942 canvas at a device pixel ratio of 2. **It is not a phone**, and #397's performance target is still to be agreed with the owner on a measured device.

**Not verified, and only the owner can:** play on an actual iPhone and Safari; the sound with and without headphones; edge swipes and scroll conflicts on a real touch screen; whether the numbers above feel right.

## Delivery boundaries

Branch from `origin/main`. Keep conveyor logic in its own focused modules instead of duplicating or rewriting Ranked. No React migration is approved. No backend or schema change beyond the best-score table in stage 4, and no leaderboard data work before the stage 6 privacy decision. No live test accounts, data wipes or deployments as a side effect of merging. This document approves rules and sequence; it does not approve a release.
