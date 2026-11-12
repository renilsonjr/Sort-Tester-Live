# Login ID auth plan (v2)

**Status:** Approved direction for implementation (2026-11-11). Supersedes password-based authentication/recovery assumptions in earlier ranked planning docs (e.g. password/`pwdlib[argon2]` login, “current password” reauthentication, and self-service password recovery flows described in `docs/superpowers/specs/2026-11-07-ranked-security-operations-design.md`, `docs/superpowers/specs/2026-11-07-ranked-decision-record.md` Decision 14/Q10, `docs/superpowers/specs/2026-11-07-ranked-worked-examples.md` example 23, and related roadmap/issue text). Competition/privacy rules not listed here remain governed by their controlling docs unless they conflict with this plan.

## Decisions (locked)

- **Database:** stay on **PostgreSQL**; build on existing Alembic/psycopg foundations and completed identity/game schema work.
- **Login:** login page accepts **only the account’s login ID** (no password, no username entry required to authenticate).
- **Credential issuance:** on account creation the system generates a **login ID** and shows it **once**. The user must save it; the system must not rely on being able to display the raw value again.
- **Format:** a **short, grouped code that is easy to type** (human-friendly), with enough entropy to resist online/offline guessing given it is the sole factor. Recommended shape (tunable at implementation): 12–16 characters from an unambiguous alphabet (e.g. Crockford base32 without `I,L,O,U`), rendered in groups (e.g. `ABCD-EFGH-JKLM-NPQR`).
- **Separation of identifiers:**
  - **Internal owner key:** `accounts.id` (UUID) remains the stable internal identifier (unchanged).
  - **Public/display identity:** `username` + permanent `tag` (and any shown `username#TAG`) remain the identity shown beside names (unchanged in meaning).
  - **Login credential:** the generated login ID is a **separate secret** used only to authenticate/access the account; it is not the display name/tag.
- **Recovery:** if a user loses the login ID, **the admin (owner) grants/regenerates access** for that account (no self-service password reset). Recovery must restore access only to the same existing account and must not expose or require the old secret; follow existing “trusted prior participant/account link” / in-person verification posture where applicable and never create substitute prize eligibility.
- **Sensitive-action reauthentication:** actions previously requiring “current password” (e.g. account deletion confirmation flows) must instead require **recent reauthentication with the login ID** (or an equivalent short-lived reauth proof bound to the session), with the same ownership/CSRF/explicit-confirmation/irreversibility expectations.

## Security model and implications

- The login ID is a **bearer secret** (possession = access). Treat as a high-value credential: generate with a CSPRNG, show once over HTTPS, never log, never include in URLs, and protect endpoints with strict rate limiting / attempt throttling and generic failure responses (no account/ID enumeration).
- **Storage:** store **only a verifier** of the login ID (e.g. Argon2id hash with per-secret salt, parameters benchmarked for the target host) plus any non-secret metadata needed for issuance/rotation. Do **not** store the raw login ID. Because it is shown once, “view again” is not supported.
- **Lookup vs verification:** short grouped codes are for entry, but efficient login must not require scanning/verifying against all accounts. Implementation should use a **lookup component + verifier** pattern, for example: generate a random secret portion, derive/store a non-secret indexed lookup key (or store a random public selector) alongside a strong hash of the full/secret value; on login, parse/normalize the entered code, locate by lookup key, then verify the hash in constant-time style comparison semantics. Exact scheme chosen during implementation, but it must avoid plaintext storage and avoid leaking validity via timing/observable differences.
- **Sessions:** after successful login issue an **opaque server-side session** (PostgreSQL-backed), host-only Secure HttpOnly SameSite cookie as appropriate, server-enforced idle/absolute lifetime, rotation on privilege changes and on credential regeneration/recovery, and revocation on logout/recovery/deletion. No session tokens in localStorage.
- **Admin recovery:** admin action issues a **new login ID shown once** (to the verified person) or another one-time handoff that results in a new login ID; prior credential and active sessions/tokens are revoked on completion. All recovery actions must be auditable in server-side admin records appropriate to existing privacy constraints.

## Data model changes (additive, on top of current schema)

> `accounts` today: `id` (uuid PK), `username`, `username_lower` (unique), `tag` (unique), `created_at`, `deleted_at` — no credential fields.

Proposed migration(s) (shape to be finalized in implementation PR/issue):
- Add login credential storage for accounts (either columns on `accounts` or a dedicated `account_credentials`/`account_login` table linked 1:1 to `accounts.id` with cascade). Store at minimum:
  - a **lookup/indexable identifier** derived from the issued code (non-secret, unique) to find the candidate row, and
  - a **verifier hash** (and algorithm/params metadata if not implicit) of the secret login ID,
  - issuance metadata (`created_at`, optional `rotated_at`, `revoked_at`/active flag) to support one-time issuance and admin regeneration.
- Do not repurpose `accounts.id` (UUID) or `tag` as the login secret.
- Keep `participant_links`, `season_markers`, `emails`, and attempt/score tables unchanged in meaning except where flows reference “password” (none in schema today).
- Session storage: add/confirm server-side session table(s) when implementing auth (opaque id/hash, `account_id`, expiry, rotation/revocation fields) consistent with PostgreSQL-first approach.

## Application flows (to implement)

1. **Create account**
   - Create `accounts` row (existing identity rules: username/tag/UUID) and generate login ID.
   - Return/show login ID **once** with explicit save/copy warning; never persist raw value.
   - (Optional UX) confirm user saved it before finalizing view, but server must not be able to redisplay.
2. **Log in**
   - Single input: login ID. Normalize grouping/case per format rules, lookup candidate, verify hash.
   - On success create server-side session; on failure return generic error and apply throttling.
3. **Log out**
   - Revoke server session.
4. **Admin grant/regenerate access (lost login ID)**
   - Owner/admin-only, authenticated and authorized flow; verify person/account per trusted process.
   - Generate and deliver/show a **new** login ID once; revoke old credential and existing sessions.
5. **Delete account (self-service)**
   - Require authenticated session + recent **login ID reauthentication** + ownership + CSRF + explicit unchecked acknowledgment/final action (preserve existing irreversibility, withdrawal-before-finalization, and purge rules from settled policy, replacing password reauth only).
6. **Guest/Practice**
   - Unchanged: guests can continue Practice/study without login where currently intended.

## Implementation sequence (build order, incremental)

1. **Spec/doc alignment (this change set):** record this plan, mark password-based auth text as superseded, update README/roadmap/pilot wording to “login with generated account/login ID (shown once)”.
2. **Auth credential schema:** migration + tests for login credential storage/uniqueness/verification hooks (no plaintext), integrated with existing test harness/scratch DB.
3. **Session + auth API:** create-account (issue-once), login, logout, session middleware/CSRF/rate limiting, admin-only regenerate/grant endpoint or operator flow.
4. **Frontend flows:** login screen (login ID only), account creation reveal-once UX, reauth prompt for deletion, admin recovery UI/tooling as scoped.
5. **Policy/ops hardening:** audit logging for admin recovery, throttling/lockout tuning, backup/restore considerations unchanged for PostgreSQL (no file-lock issues), and update security/decision docs to finalized behavior once implemented.

## Known divergences to resolve in repo/docs/issues (tracker)

- `README.md`, `docs/superpowers/specs/2026-11-06-ranked-pilot-design.md`: “Log in” flow must reflect login-ID-only (no password) when implemented.
- `docs/superpowers/specs/2026-11-07-ranked-decision-record.md` (Decision 14, Q10 text/status): replace password recovery/current-password/verified-email-as-password-reset assumptions with login-ID + admin-granted recovery and login-ID reauth.
- `docs/superpowers/specs/2026-11-07-ranked-security-operations-design.md`: replace password hashing rules, password-based recovery handoff, and “current-password reauthentication” deletion gate with login-ID credential, issuance-once, admin regeneration, and login-ID reauth.
- `docs/superpowers/specs/2026-11-07-ranked-worked-examples.md`: update example 23 (forgotten password) to lost login ID + admin-granted access.
- `docs/superpowers/plans/2026-11-06-ranked-roadmap.md` and GitHub **#7** (“Add employee registration, sessions, and account access controls”): scope must reflect login-ID auth (no passwords) and admin recovery; keep PostgreSQL/sessions/ownership goals.
- `docs/security/2026-11-06-static-review.md` and similar notes: future auth wording should not assume passwords.
- Any future UI/mockup issues (#10/#15/#16/#17) must show single-field login ID and one-time reveal at creation.

**GitHub issues (checked 2026-11-11):** open issues relevant to auth include **#7** (registration/sessions/access controls — currently written around username/password/verified-email recovery in its body) and downstream dependents (#8/#10/#11/#24/#26/#27). Issue bodies/descriptions should be updated when implementation is scheduled to match this plan (live issue edits are outside this repo change set unless done via `gh`).
