# Ranked Interactive Feedback (Glow & Synthesized Audio) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate instant visual feedback (green/red glow with pulse/shake) and zero-latency synthesized audio (SFX and background music) on answer selection during Ranked mode.

**Architecture:** Pure client-side enhancement. A self-contained Web Audio synthesizer module (`src/sound.js`) handles audio generation without external network assets; quiz styles and view handlers (`src/quiz.js`) apply responsive visual feedback and synchronize reactions with the 3D avatar iframe while preserving all backend scoring and settlement invariants.

**Tech Stack:** Vanilla JavaScript (ES modules), Web Audio API, CSS3 Animations, Node.js test runner (`node --test`).

---

## Files Changed / Created

- **Create:** `src/sound.js` — Audio synthesizer module (Web Audio API, sound effects for correct/incorrect, ambient focus BGM loop, localStorage mute persistence).
- **Create:** `tests/sound.test.mjs` — Unit tests for sound engine states and audio context handling.
- **Modify:** `src/quiz.js` — Connect belt button click handlers to visual classes, audio triggers, and avatar reaction messages.
- **Modify:** `index.html` (or quiz CSS) — Add `@keyframes` for `.belt-correct` and `.belt-incorrect`, plus `prefers-reduced-motion` fallbacks.
- **Modify:** `tests/ranked-play.test.mjs` — Ensure ranked quiz test suite asserts the feedback classes and flow.

---

## Tasks

### Task 1: Synthesized Web Audio Module (`src/sound.js`) — `TDD`

**Files:**
- Create: `tests/sound.test.mjs`
- Create: `src/sound.js`

- [ ] **Step 1: Write failing test for sound module:**
  Create `tests/sound.test.mjs` checking audio enabled toggles, localStorage persistence, and function signatures (`playCorrectSfx`, `playIncorrectSfx`, `startBgm`, `stopBgm`).
- [ ] **Step 2: Run test to confirm failure:**
  `node --test tests/sound.test.mjs`
- [ ] **Step 3: Implement `src/sound.js`:**
  Build clean Web Audio API synthesizer matching the approved behavior from the prototype.
- [ ] **Step 4: Run test to confirm pass:**
  `node --test tests/sound.test.mjs`
- [ ] **Step 5: Commit:**
  `git commit -m "feat(audio): add zero-latency Web Audio sound engine for quiz feedback"`

---

### Task 2: CSS Animation Styles for Belt Answers — `TDD`

**Files:**
- Modify: `index.html` / `quiz-review.css` (or main stylesheet)
- Create: `tests/quiz-feedback-style.test.mjs`

- [ ] **Step 1: Write test for CSS keyframes and reduced-motion fallback:**
  Ensure `.belt-correct` and `.belt-incorrect` classes exist and define reduced-motion overrides.
- [ ] **Step 2: Implement CSS rules:**
  Add `@keyframes correctGlow` and `@keyframes incorrectShake`, button transform states, and `prefers-reduced-motion: reduce` rules.
- [ ] **Step 3: Verify tests pass:**
  `node --test tests/quiz-feedback-style.test.mjs`
- [ ] **Step 4: Commit:**
  `git commit -m "style(quiz): add glow and shake feedback animations with accessibility support"`

---

### Task 3: Integrate Feedback & SFX into `src/quiz.js` — `TDD`

**Files:**
- Modify: `src/quiz.js`
- Modify: `tests/ranked-play.test.mjs`

- [ ] **Step 1: Update quiz tests:**
  Verify clicking an answer marks the element with the proper feedback class and triggers the avatar postMessage.
- [ ] **Step 2: Wire `src/quiz.js`:**
  Import `src/sound.js`, trigger `playCorrectSfx()` / `playIncorrectSfx()`, add `.belt-correct` / `.belt-incorrect`, and trigger avatar reaction.
- [ ] **Step 3: Run full frontend test suite:**
  `node --test tests/*.test.mjs`
- [ ] **Step 4: Commit:**
  `git commit -m "feat(quiz): wire interactive visual and sound feedback to answer selection"`

---

### Task 4: Manual Verification in Browser

- [ ] **Step 1:** Run local server `backend/.venv/bin/uvicorn backend.main:app --reload --port 8000` (or `python3 -m http.server 8000`).
- [ ] **Step 2:** Open `http://localhost:8000` and start a quiz.
- [ ] **Step 3:** Confirm green glow + victory chime on correct belt, red glow + shake on incorrect belt, and sound mute button behavior.
