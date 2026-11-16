# Home artwork — golden hat podium

Status: approved visual mock (owner, 2026-11-15); integration prepared for PR review on 2026-11-16. Deployment remains separate.

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

## Integration decisions — 2026-11-16

- Targets `codex/ranked-mode` only, as requested; `main` remains unchanged.
- Ships `assets/home-podium.jpg`, optimized to 860 × 484 px (about 113 KB),
  instead of the 1.9 MB library source. The whole image keeps its aspect ratio.
- The shared guest/member home replaces its avatar with the artwork. Quiz
  and feedback avatars remain unchanged.
- English alternative text transcribes the message and describes the hat and
  podium; Spanish alternative text translates it. The visible artwork remains
  English in both languages.
- The artwork advertises the existing up-to-three-hat prize feature (#12/#24).
  Eligibility, tie-breaks, fewer-winner cases and finalization still follow
  [[2026-11-07-ranked-decision-record]]; the image grants no prize by itself.
- Embedded small print remains small at phone width. The owner reviewed the
  full-image mock; this integration preserves that artwork without cropping.

## Browser verification — 2026-11-16

Verified against the local FastAPI app with an isolated fictional-data database:
- Guest and signed-in home at 320/390 px: artwork loads, no horizontal overflow.
- Spanish selection translates the image alternative text.
- Member navigation reaches Practice and returns Home with the poster intact.
- Quiz/feedback asset references are unchanged; no prize logic changed.

The visible image text remains English and its smallest text is small on phones.

## Owner adjustment — 2026-11-16

Remove the visible “Practice the chart” heading above the artwork. The image
leads the home; a visually hidden localized “Home” heading retains the page
heading for assistive technology.
