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
- The quiz feedback comparison block keeps a cold blue surface. Slice 2.

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

## Checks

- `node --test 'tests/*.test.mjs'`: 395 passing before and after.
- Home, study, name entry and the deck picker at 320 px and 375 px: nothing
  cut off, no sideways scroll, no JavaScript error.
