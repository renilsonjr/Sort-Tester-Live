# Sort Lab visual library

Standalone visual review prototype. Start from [[2026-11-14-visual-library-design]] and [[2026-11-14-visual-library]]. The actual app is unchanged.

## Open

From the repository root:

```sh
python3 -m http.server 8014 --bind 127.0.0.1
```

Open `http://127.0.0.1:8014/mockups/design-library/`.

- **Foundations:** proposed surface/action colors, preserved routing colors, local Nunito, spacing and corner scale.
- **Components:** 12 specimen groups, including buttons, fields, selections, cards, navigation, belts, timers, messages, results, empty/loading states and a confirmation dialog.
- **Screens:** 23 searchable/refreshed screen specimens with source and flow-status metadata. Screen buttons follow demonstration paths.
- **Motion & badges:** approved rank artwork and five replayable interface motion examples.

All screen content is fictional and for appearance review. The catalog does not make API requests, create accounts, send tickets, export files, clear real logs or save attempts. Source/status labels identify the underlying flow; they do not imply approval or production implementation of the visual refresh. Use the current worksite chart for actual routes.

## Files

- `index.html` — section shell and approved badge markup.
- `library.css` — proposed shared visual tokens, components and responsive layouts.
- `library.mjs` — specimens, screen templates, navigation and preview-only interactions.
- `catalog.mjs` — searchable screen inventory and owning-source metadata.
- `badges/` — approved rank concepts; prompts in [[badge-prompts-2026-11-14]].

## Verification — 2026-11-14

- `node --test mockups/design-library/catalog.test.mjs`: 2 tests passed; screen coverage/status and combined search/status filtering.
- JavaScript syntax checks and `git diff --check` passed.
- Chrome: opened all 23 specimens at desktop and 320 px; no document horizontal overflow. All four library sections also checked at 320 px.
- Search/status filters, route search/no-results state, saved-ID button gating, busy button completion and sample dialog checked.
- Dialog opens on the safe action; Escape closes and returns focus to its trigger.
- Reduced-motion checkbox synchronization and animation replay checked. No browser console errors observed during this session.

## Remaining review limits

Screen refreshes are approximations, not mounts of production components. Full Spanish specimen copy is not implemented; the preview language control explains this rather than pretending to translate. Ranked, Leaderboard, Profile and Tickets remain clearly labeled concepts, with final content undecided. No claim of complete accessibility conformance or slower-device performance validation is made.

## Avatar retired — 2026-11-19

The blue parcel avatar (Blender model, rendered poses, 3D viewer and the quiz
approval mock `quiz-review.html`) was removed from the app and from this
library at the owner's request: it did not render reliably on iOS Safari and
took space the quiz needed for the route and the belts. The quiz now shows the
route large with the belts directly under it. The files remain in git history
(last present in the commit before this note) if the model is ever wanted
again.

## Home artwork proposal — 2026-11-15

Open `home-artwork-review.html` from Screens to compare the supplied golden hat podium artwork with the earlier home. Based on the home in `mockups/entry-navigation.html`; preserves its headings, announcements, Practice/Ranked actions and navigation. Visitor and season-notice controls demonstrate the existing home states. The poster uses its complete original aspect ratio without cropping; embedded text may be small on phones. Other-screen buttons show a preview notice.

The owner approved this visual mock on 2026-11-15. Approval covers the supplied image replacing the home avatar in this layout; production integration remains separate. The artwork does not change the implemented prize rules. Source artwork: `home-artwork/golden-hat-podium.png`. Issue draft: [[home-artwork/issue-draft]].
