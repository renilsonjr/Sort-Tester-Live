# Applying the visual library to the app

The mock redesign was approved, so the same look now goes into the app
itself. This is the plan and the record of how it is being applied.

## Where this lands, and where it does not

**The redesign targets the monolith only.** Work branches from
`codex/ranked-mode`, which is what the Azure Container Apps staging monolith
is built from. GitHub Pages serves `main` at `/`, and `main` carries none of
this: it is not an ancestor of the redesign branches, so merging them into
`codex/ranked-mode` cannot change the live page.

The owner settled this on 2026-11-14: the app that is live today does not
need the new look; the redesign is for the monolith when it is ready.

**Worth knowing for later:** the day `codex/ranked-mode` is merged into
`main`, the redesign goes live with it. That merge is the moment the change
becomes visible to the people using the app, and it should be a deliberate
decision rather than a side effect.

## Slices

1. **Base and the calm screens** (this slice): one palette, then home,
   study, name entry and the deck picker.
2. **The quiz screens**: the timed card, feedback for right and wrong, the
   results and the shift log.
3. **The mascot**: replacing `assets/parcel-buddy.jpg` and the three
   `assets/quiz-*.jpg` moods with the approved Blender avatar, animated in
   the quiz only.
4. **The sign-in panel** in `src/auth.js`.

## Slice 1 — what changed

- **Three stacked `:root` blocks became one.** The file carried the original
  palette, then a "Twilight redesign" override, then a "friendly study
  concept" override. Each visual change had been stacked on the last, so
  changing a colour meant working out which layer was winning. There is now
  one block, holding the library tokens, with a comment saying so.
- Home, study, name entry and the deck picker retargeted to the warm
  palette.
- **Primary actions are gold with dark text**, following the library.
- **The focus ring is the library blue at 4 px offset**, on buttons, inputs,
  selects and disclosure summaries.
- The four decorative bars in the hero follow the warm palette. They are not
  belts and carry no routing meaning; the comment in the file says so.

**Belt colours are untouched.** They come from `BELT_STYLE` in
`src/belts.js` and are routing information, not decoration.

### Scope that spilled, deliberately

`.primary` is one rule for the whole file, so making it gold also changed the
quiz's Next button and the sign-in panel, which belong to slices 2 and 4.
Splitting it per screen would have meant temporary exceptions that someone
has to remember to remove. The spill is noted here rather than hidden.

### Known ugly, pending its slice

- The home mascot is still `assets/parcel-buddy.jpg`, whose pale blue
  backdrop now sits in a warm page. Slice 3.
- The quiz feedback comparison block keeps a cold blue surface. Fixed in
  slice 2 below.

## Slice 2 — the quiz screens

- The feedback comparison block and the remaining plain whites moved to the
  warm surfaces.
- **Belt answer colours are untouched**, from `BELT_STYLE`.

### Gold cannot mean "button" where yellow means "belt"

The library's gold is `#f4bd38`; the YELLOW belt is `#f6d33c`. They differ by
2, 22 and 4 per channel — side by side on a phone they read as one colour.
In the app gold now means "this is the primary action", while YELLOW means
"this package goes to the yellow belt". On the feedback screen a YELLOW chip
would sit beside a gold Continue: information and action, identical.

**Settled with the owner on 2026-11-14:** on quiz screens the primary action
is brown; the calm screens keep the library's gold. On a quiz screen, yellow
therefore always means a belt and never a button.

This leaves two primary-button treatments in one app on purpose. The rule in
`index.html` carries a comment saying so, so nobody "fixes" it back to gold.

## Slice 3 — the mascot

The four photos (`parcel-buddy.jpg` and the three `quiz-*.jpg`) are replaced
by the approved Blender avatar: idle on home, thinking on the question,
correct and incorrect on feedback. The old files are deleted, and the
backend static-file test now names one that exists.

### Re-rendered on a warm backdrop

The library's studio renders are nearly black at the top — the world
background is dark grey — which put a heavy dark block in a cream page. The
owner chose to fix it at the source rather than crop it or accept it.

`mockups/design-library/blender-avatar/render_app_poses.py` opens the
approved `.blend` read-only, sets only the world background to the app's warm
surface, and writes the four poses elsewhere. **It never saves the `.blend`
or the `.glb`**, so the approved model and the library's own renders are
untouched. Re-running it reproduces the app's artwork.

Note for anyone changing it: `scene.world.color` alone does nothing when the
world uses nodes; the background node's colour has to be set too.

### Weight

8–9 KB per pose at 600 px, against 296–329 KB for the four photos they
replace. The quiz loads about a megabyte less than before.

### Animation

Still none in the app. The owner settled that the avatar animates in the
quiz only, and the quiz question screen re-renders once per question, so an
iframe-mounted model would reload 2 MB every question. Doing it properly
means mounting the viewer once outside the re-rendered node and sending it
the state. That is its own piece of work and is not in this slice.

## Slice 4 — the sign-in panel

The panel already inherited the warm palette from slice 1, so this slice is
about what it says, not its colours. It was a title and three bare buttons
— Log in, Create account, Continue as guest — with nothing explaining the
difference.

It now follows the entry screen the owner approved in
`mockups/entry-navigation.html`: two cards that each say what that way in
gives you. Log in and Create account sit in the account card; Continue as
guest sits in the no-account card, which states plainly that nothing is
saved.

- **The button ids are unchanged**, so the panel's own behaviour and the
  `auth-gate` tests still find them.
- The avatar is hidden below 700 px of height, so both cards and their
  buttons always fit without the panel scrolling.

### One wording change worth flagging

The approved mock's account card is about Ranked: "Log in to play Ranked
quizzes, earn a badge and see the leaderboard." None of that is built yet,
so the panel would be promising features that do not exist. The card says
"Log in to keep your quiz history on this account" instead — true of the app
as it stands today. When Ranked ships, this is the line to revisit.

## Checks

- `node --test 'tests/*.test.mjs'`: 395 passing before and after.
- Home, study, name entry and the deck picker at 320 px and 375 px: nothing
  cut off, no sideways scroll, no JavaScript error.
- A whole quiz played through in a browser at 375 px: question card, timer,
  belt answers, feedback for a wrong answer and the Continue action. No
  sideways scroll and no JavaScript error.
- `backend.tests.test_static_frontend`: 5 passing after the asset rename.
- Home and the question screen checked with the new renders loaded.
- The sign-in panel at 320 px and 375 px: both cards and their buttons fit
  without the panel scrolling, the login form opens and cancels, and
  Continue as guest still enters the app.
