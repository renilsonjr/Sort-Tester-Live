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
- **Motion & badges:** approved blue/front-facing Blender avatar with animation preview and `.blend`/`.glb` downloads; approved rank artwork and five replayable interface motion examples.

All screen content is fictional and for appearance review. The catalog does not make API requests, create accounts, send tickets, export files, clear real logs or save attempts. Source/status labels identify the underlying flow; they do not imply approval or production implementation of the visual refresh. Use the current worksite chart for actual routes.

## Files

- `index.html` — section shell and approved mascot/badge markup.
- `library.css` — proposed shared visual tokens, components and responsive layouts.
- `library.mjs` — specimens, screen templates, navigation and preview-only interactions.
- `catalog.mjs` — searchable screen inventory and owning-source metadata.
- `blender-avatar/` — latest approved Blender model, exports, rendered poses and animation preview.
- `badges/` — approved rank concepts; prompts in [[badge-prompts-2026-11-14]].
- `vendor/` — Three.js 0.170.0 and MIT license, locally vendored for this prototype.

## Verification — 2026-11-14

- `node --test mockups/design-library/catalog.test.mjs`: 2 tests passed; screen coverage/status and combined search/status filtering.
- JavaScript syntax checks and `git diff --check` passed.
- Chrome: opened all 23 specimens at desktop and 320 px; no document horizontal overflow. All four library sections also checked at 320 px.
- Search/status filters, route search/no-results state, saved-ID button gating, busy button completion and sample dialog checked.
- Dialog opens on the safe action; Escape closes and returns focus to its trigger.
- Mascot initialization/tab return, reduced-motion checkbox synchronization and animation replay checked. No browser console errors observed during this session.

## Remaining review limits

Screen refreshes are approximations, not mounts of production components. The 3D model approximates the source JPG; screen specimens use still renders from the approved Blender avatar. Full Spanish specimen copy is not implemented; the preview language control explains this rather than pretending to translate. Ranked, Leaderboard, Profile and Tickets remain clearly labeled concepts, with final content undecided. No claim of complete accessibility conformance or slower-device performance validation is made.

## Approved avatar — 2026-11-14

The owner approved the more blue, front-facing Blender version and requested its inclusion in the library. Use `blender-avatar/parcel-buddy-reference-v3.glb` and its editable `.blend` as the visual implementation reference. Start with [[blender-avatar/README]] for animation ranges and remaining rig/gesture limitations. Previous procedural avatar versions and their captures were removed at the owner’s request. Only the latest approved blue, front-facing Blender version remains in the library.

## Quiz mock with approved avatar

`quiz-review.html` is the approval mock for the Blender avatar integrated into quiz layouts. It covers question/Thinking, correct/Cheer, incorrect/Oops, timeout/Oops and results/Idle, with answer buttons and a pause dialog. Data and timer are fictional/static and no attempts are stored. The production quiz remains unchanged. Open it from Screens → Review quiz with animated Blender avatar. The embed uses the same approved GLB via `blender-avatar/embed.html`; no older avatar was reintroduced.

## Quiz mock approval — 2026-11-14

The owner explicitly approved `quiz-review.html`: quiz layout, avatar position, and the demonstrated reactions in question, correct, incorrect, timeout and results screens. Use this mock together with the approved blue, front-facing Blender model as the visual implementation reference. See [[blender-avatar/README]] for model/animation limitations.

Approval covers the visual mock. Its fictional route data, static timer, sample scores and manually advanced feedback are review aids, not changes to production quiz rules. Preserve existing real quiz timing, scoring, automatic correct-answer advance and persistence when implementing the appearance. The production app has not been modified by this approval record.

## Home artwork proposal — 2026-11-15

Open `home-artwork-review.html` from Screens to compare the supplied golden hat podium artwork with the current home avatar. Based on the home in `mockups/entry-navigation.html`; preserves its headings, announcements, Practice/Ranked actions and navigation. Visitor and season-notice controls demonstrate the existing home states. The poster uses its complete original aspect ratio without cropping; embedded text may be small on phones. Other-screen buttons show a preview notice.

The owner approved this visual mock on 2026-11-15. Approval covers the supplied image replacing the home avatar in this layout; production integration remains separate. The artwork does not change the implemented prize rules. Quiz avatars and production files are unchanged. Source artwork: `home-artwork/golden-hat-podium.png`. Issue draft: [[home-artwork/issue-draft]].
