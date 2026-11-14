# Visual library implementation plan

**Goal:** Expand the approved review page into a navigable design catalog.

**Architecture:** Standalone HTML/CSS/ES modules under `mockups/design-library/`; shared visual tokens and review templates. No production app or backend integration.

**Spec:** [[2026-11-14-visual-library-design]]

## Constraints

Brown/gold/warm-white refresh, local Nunito, unchanged belt colors, no referenced company name or logo in preview UI, fictional data, source/status labels. Retain approved badge and mascot files. Additive preview changes only.

## Tasks

- [x] Add screen inventory with source/status metadata and filters; verify existing/approved/concept groups and search.
- [x] Extend index with Foundations, Components, Screens, Motion navigation and shared CSS. Add interactive specimens and screen rendering, accessible dialog and reduced-motion control.
- [x] Verify browser interactions, 320/375 px layout, keyboard dialog behavior, mascot tab switching, syntax and whitespace; record remaining limits.

## Review focus

Hidden 3D stage sizing; long labels on phones; keyboard focus after screen changes; sample forms must never submit credentials; unfinished screen content must be labeled.
