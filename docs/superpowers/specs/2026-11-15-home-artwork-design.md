# Home artwork — golden hat podium

Status: approved visual mock (owner, 2026-11-15). Not integrated into the app.

## What was approved

The supplied Golden Hat Podium artwork replaces the avatar in the **home**
position, in the home layout as it stands. The mock is
`mockups/design-library/home-artwork-review.html`, built from
`mockups/entry-navigation.html`, and the source image is
`mockups/design-library/home-artwork/golden-hat-podium.png`. The approval
covers the appearance only; see [[../plans/2026-11-14-visual-library]] and
`mockups/design-library/README.md` for the library this belongs to.

## Scope

Only the home avatar changes. The quiz and feedback avatars stay on the
approved blue front-facing Blender model
(`mockups/design-library/blender-avatar/`), and the production quiz is
untouched.

## Acceptance criteria

- The home avatar is the artwork; quiz and feedback avatars are unchanged.
- The whole image is shown at phone widths, uncropped and undistorted.
- Guest and member navigation, the announcements block and the season-start
  notice all still work and still read correctly around it.
- The text inside the artwork has meaningful alternative text, since a screen
  reader gets nothing from the image itself.
- The prize wording in the artwork is confirmed against the implemented prize
  rules before it ships — the picture does not change those rules.
- Image weight and the legibility of its embedded text are reviewed at phone
  width before production integration.

## Open questions for the owner

- Which build does this land in: `codex/ranked-mode` (the monolith redesign)
  only, or also the live GitHub Pages `main`? The standing instruction has
  been that `main` does not change.
- The PNG is ~1.9 MB. Does it get compressed, or served at a smaller size for
  phones, before it reaches the home screen of a real player?
