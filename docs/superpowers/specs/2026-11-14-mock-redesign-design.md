# Applying the visual library to the navigation mock

The owner asked for the approved visual library to be applied as a redesign of
the whole application, starting by redoing the mockups built for #15 and #16
so they can be reviewed in the new look.

This changes `mockups/entry-navigation.html` only. No app file (`index.html`,
`src/`, `backend/`) changes, and nothing here is a completed feature.

## Where the look comes from

`mockups/design-library/` and
[its design](2026-11-14-visual-library-design.md): the approved refresh of the
rounded design in brown, gold and warm white. Tokens taken from
`library.css`:

| Token | Value | Used for |
|---|---|---|
| page | `#f7f3ec` | behind the phone frame |
| surface | `#fffdf8` | cards and the frame |
| ink | `#35271e` | text |
| muted | `#6e5c4d` | secondary text |
| brand | `#38261b` | headings, links, strong marks |
| gold | `#f4bd38` (edge `#b47d15`) | the primary action, active markers |
| soft | `#f7eac7` (edge `#d6bc75`) | tinted surfaces |
| line | `#ded4c5` | borders |
| focus | `#175e94` | the focus ring, 3 px at 4 px offset |
| success / danger | `#226442` / `#a12d2d` | winners / deletion |

**Belt colours are untouched.** They are routing information, not decoration,
as the library's own design states.

## Decisions made while applying it

- **The primary action is gold with dark text**, following the library, not a
  brown fill.
- **The sort-change announcement moved onto the plain surface** with a gold
  left edge. In the warm palette it had become a second tinted card sitting
  next to the Ranked card, and the two read as a pair.
- **The balance bar is brown on a warm track.** Gold on a gold-tinted track
  nearly disappeared.
- **Leaderboard winners stay green.** In this palette gold now means "primary
  action", so a gold winner row would read as something to tap.
- **Deletion keeps red.** It is the one place that leaves the warm palette,
  and it still says "Delete account" in words.
- **Active markers keep a shape as well as a colour**: the bottom tab and the
  profile tab each keep an underline, and the current badge keeps its "you
  are here" text.

## The approved artwork

- The five rank badges appear in the Profile ladder and beside the balance,
  and the badge art follows the balance shown.
- The Blender avatar greets the player on the home and practice screens.
- **Small copies live in `mockups/assets-sm/`** (580 KB in all). The
  originals are 1000–1300 px and over a megabyte each; a phone should not
  load 7 MB of artwork to look at a mock. The originals stay in the library
  as the source.
- **The avatar render carries its own backdrop**, so it is framed as a
  rounded portrait rather than floated on the page. Floating it showed a grey
  rectangle. A truly free-standing avatar needs a new Blender render with a
  transparent background, not a CSS change.

## Animation (settled 2026-11-14)

The avatar does animate: `blender-avatar/parcel-buddy-reference-v3.glb`
carries baked tracks for idle, thinking, correct and incorrect on one
timeline, and `blender-avatar/embed.html` plays them. Checked in a browser:
the model loads, the loop runs, the pose changes between frames, and it holds
still when the viewer asks for reduced motion.

**The owner settled that the avatar animates in the quiz only.** The quiz is
where a reaction means something; everywhere else the still renders are used.
The reason is weight: the model is 1.3 MB and the bundled three.js is 675 KB,
about 2 MB more on a phone, which matters on a warehouse connection.

`mockups/design-library/quiz-review.html` already uses the animated embed and
is the approved quiz mock, so nothing had to be built for this decision.

Known limits, from the avatar's own README: there is no production skeletal
rig and no separate facial rig, and the arms do not yet reproduce the
raised-hand cheer in the reference.

## Checks

At 320 px and 375 px, across entry, login, lost login ID, guest home,
practice, member home, Ranked, Leaderboard, Profile, deletion and tickets:
no screen scrolls sideways, no image fails to load, and no JavaScript error
is raised. The focus ring is the library blue at 4 px offset on buttons,
inputs, selects, textareas and disclosure summaries.

## Still open

- What belongs in git long term: `mockups/design-library/` carries 16 MB of
  badge art, avatar renders, a `.blend` source and a vendored three.js.
  Deciding source from generated output is worth doing before this becomes
  part of the app proper.
- Applying the library to the real app (`index.html`, `src/`) has not
  started. This slice redesigns the mock so the look can be reviewed first.
