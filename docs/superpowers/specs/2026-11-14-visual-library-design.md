# Visual library design

## Intent and agreed direction

The owner requested a visual review library covering screens, buttons, components and animation. They selected a refresh of the existing rounded design using brown, gold and warm white, without the referenced company's name or logo. They approved the five generated rank badges and the blue mascot's four animation directions. On continuing, they authorized expanding the library with screens and interaction states.

## Approach

Extend the existing standalone library under `mockups/design-library/` with four sections: Foundations, Components, Screens, Motion. Retain the approved mascot and badge assets. Alternatives considered: a more corporate redesign (not selected), or changing the production app directly (unsuitable while reviewing). This is a design review prototype, not a production component package.

## Scope

Inventory the current browser screens in `src/app.js` and `src/auth.js`, plus the approved navigation in [[2026-11-14-entry-navigation-mockups-design]]. Show proposed refreshed versions with fictional sample data, linking each to its owning source. Clearly distinguish existing flows, approved navigation mockups and undecided placeholders. Preserve belt colors from `src/belts.js`; branded surface colors must not replace routing colors.

Foundations: semantic colors, local Nunito typeface, spacing, corners and motion durations. Components: action variants and states, fields, language/service selection, navigation, cards, belt chips, timers, result summaries, alerts, empty states, confirmation dialog, disclosure and loading. Screens: entry/auth, guest/member navigation, study, practice selection, question/feedback/timeout, stop, results/log, and conceptual Ranked/Profile/Tickets paths. Motion: existing 3D character plus replayable UI motion.

## Constraints and builder decisions

No production app changes, backend calls, real accounts, saved quiz results or changes to sorting rules. Work stays in the existing review folder. Existing files may only be changed after explaining the change to the owner. Use real buttons, labels, visible focus, dialog focus restoration, responsive 320 px layout and reduced motion. Never represent a UI specimen as an implemented feature. A live study-data sample may import current chart/belt constants; sample content is labeled as visual review only.

## Verification

Check browser navigation and interactive specimens, source/status metadata, mobile overflow, modal keyboard handling, keyboard focus, reduced motion and mascot availability after switching sections. Check syntax and whitespace. Preserve existing mascot controls and approved assets.
