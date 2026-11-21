# Account deletion mockups (Issue #16, slice 3)

Third slice of #16. Unlike the earlier slices, the behaviour behind these
screens is already built: #47 slice 3 implemented self-service deletion in
`backend/auth/deletion.py`, and [its design](2026-11-13-account-deletion-design.md)
records what the server does. These screens show that behaviour rather than
proposing new rules.

Remaining after this: Support tickets and their retention states.

This is a design for a mockup only. No app file (`index.html`, `src/`,
`backend/`) changes, and nothing here is a completed feature.

## What the server already does

From the deletion design and Decision 14:

- Deleting requires the login ID typed into the delete request itself. That
  typing **is** the reauthentication, checked at that moment.
- A wrong login ID changes nothing and is counted as a failed login. The
  answer does not say whether the account or the login ID was wrong.
- The sole owner account cannot be deleted.
- An accepted deletion clears the session, marks the account inaccessible and
  leaves it **pending purge**. There is no undo.
- The active attempt ends with no score kept, no fabricated Quit penalty, and
  no change to anyone else's points.
- Deletion is **never reported as completed**: that needs verified erasure
  from backups and outside providers, which do not exist yet (#13, #41).

## Owner choices (2026-11-14)

| Question | Choice |
|---|---|
| How many screens | Two: the question, consequences and the unchecked box first; the login ID and the final button second |
| The word "email" in the approved disclosure | Removed |

Options not chosen: one single screen, and a numbered list of consequences
replacing the approved wording.

### The "email" change

Decision 14 fixed this exact disclosure on 7 November: "Your profile, email,
quiz history and points are deleted. We keep only a private
season-ineligibility record until prizes are finalized."

The owner withdrew email from the app on 14 November, so that sentence now
promises to delete something the app never collected — which, in a privacy
notice, implies an address was held. The owner settled on removing the word.
The sentence reads: "Your profile, quiz history and points are deleted. We
keep only a private season-ineligibility record until prizes are finalized."

Everything else in the approved wording is unchanged, including the question
and the checkbox text.

### No "completed" screen

#16 asks for pending **and** completed states. The server cannot report
completed, by deliberate design. Mocking a completed screen would show the
owner something the system cannot say. Instead the mock carries a note
explaining that the state will exist once backup and provider erasure are in
place.

## Screens

Added to the existing `mockups/entry-navigation.html`, reached from Profile →
Settings → Delete account. Fictional data only.

1. **Step 1, box unchecked.** The exact question, the consequences, and the
   initially unchecked acknowledgment. Continue is disabled.
2. **Step 1, box checked.** Continue is enabled. Nothing else changes.
3. **Step 2.** A warning that this cannot be undone, the login ID field,
   Delete account and Cancel.
4. **Wrong login ID.** One message that does not reveal whether the account
   or the login ID was wrong; nothing is deleted.
5. **Pending.** After acceptance: signed out, account inaccessible, removal
   under way, no undo, and a new account would start at 0 points and Iron.
6. **Owner account.** The refusal: the sole owner cannot delete their own
   account.

## Limits

- Cancelling, leaving, going back or mistyping the login ID deletes nothing,
  and reopening the screen always resets the box to unchecked.
- No undo, no restore and no "deleted player" row are offered or implied.
- No email anywhere.
- The screens never state that deletion finished.
- Prize withdrawal and marker expiry at prize finalization are #12; the purge
  itself is #47.
- All login IDs, usernames and tags are invented.

## Checks

- **Readable labels.** Every control has a text label, and the disabled
  Continue says why it is disabled.
- **Phone layout.** Checked at 320 px and 375 px: nothing cut off, no
  sideways scroll, and the long approved sentences wrap without overflowing.
- **Keyboard and focus.** The checkbox, both buttons and the login ID field
  are reachable with Tab, work with Enter or Space, and show a visible focus
  outline. The disabled Continue is not a keyboard trap.
- **Not colour alone.** The destructive button says "Delete account"; the
  warning states the consequence in words rather than relying on red.

## Recording the review

1. Show the owner each screen in a browser at phone size.
2. Post one comment on #16 listing the approved screens and the choices.
3. Tick box 4 only once this slice is merged, noting that the completed state
   is deliberately absent.
4. Record the disclosure change in the decision record, so a reader does not
   find the approved sentence quietly altered.

## Review record (2026-11-14)

The owner reviewed the screens in a browser at 375 px, in two groups, and
approved all of them unchanged:

1. Step 1 (question, consequences, unchecked box, disabled Continue) and
   step 2 (warning, login ID, Delete account).
2. Accepted, and the owner-account refusal.

Checked before the review, at 320 px and 375 px: the box starts unchecked
with Continue disabled and a line saying why; ticking it with the keyboard
enables Continue; a wrong login ID keeps the player on step 2 with one
message and deletes nothing; a correct one reaches the accepted screen;
leaving and reopening resets the box, the field and the button; a guest sent
to the screen lands on Log in; no sideways scroll, and Tab reaches every
control with a visible outline.

## Delivery

Branch `codex/deletion-mockups` from `codex/ranked-mode`, holding this
document and the mockup changes, opened as a pull request for review.

**Ordering note:** PR #98 (slice 2) edits the same mockup file and has not
merged. The mockup changes in this slice wait for that merge; this document
does not, because it is a new file.
