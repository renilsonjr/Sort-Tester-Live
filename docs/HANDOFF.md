# Where this project is, and how to carry it on

Written 2026-11-18, at the end of a two-day security remediation. Paste
this into a new conversation to pick the work up without re-deriving it.

It says what the project is, what state it is actually in, how Renilson
and an assistant work together on it, what is next and why, and the
handful of things that cost hours to learn.

---

## 1. What the project is

**Sort Lab / Sort Tester Live** is a training quiz for parcel sorting. A
player is shown a destination and picks the belt it should go to. There
is a Practice mode that changes nothing, and a **Ranked** mode with
points, badges (Iron → Bronze → Silver → Gold → Challenger), promotion
quizzes, seasons, tie-breaks and three prizes ("hats") per season.

It is for colleagues on the owner's own shift — **Primary Sort, Twilight**
— not the public. The owner is Renilson, who is also the only operator.

Three constraints shape almost every decision:

- **Fictional data only** until a pilot is explicitly authorised.
- **Minimal collection.** No real name, no employee id, no phone, and
  (Decision 15) no email anywhere in the app. A proposal to log IP
  addresses was declined on 2026-11-17 for the same reason.
- **Azure for Students**, spending limit on. Cost is a real constraint.

The settled rules live in
`docs/superpowers/specs/2026-11-07-ranked-decision-record.md`. When a
plan and that record disagree, **the record wins** — this has already
happened twice, and both times following the plan would have been wrong.

---

## 2. Repository shape

- `main` serves GitHub Pages. **Do not change it** for app work.
- `codex/ranked-mode` is the integration branch. Everything lands there
  by pull request.
- Both are protected: PR plus green checks, admins included.
- Branches are deleted on merge; as of this writing only those two exist.

Backend is FastAPI + PostgreSQL with Alembic (head `0037`). Frontend is
vanilla JS: `src/app.js` plus `index.html`, which carries the inline CSS
and a `?v=` cache tag that **must be bumped** when `src/app.js` changes.
Infrastructure is Bicep under `infra/azure/`.

### Running the tests

```sh
SORT_TESTER_TEST_DATABASE_URL="postgresql://localhost:5432/sort_tester_unittest_scratch" \
  ./backend/.venv/bin/python3 -m unittest discover -s backend/tests
node --test 'tests/*.test.mjs'
```

**Without that environment variable, hundreds of database tests skip
silently and "OK" means almost nothing.** `pytest` is not installed.
Never run two suites against the scratch database at once.

Frontend tests read `src/app.js` and `index.html` as *text* and match
patterns; they do not execute the module.

---

## 3. How we work

This is a working agreement, learned rather than declared.

- **Explain, then do.** Renilson is learning the stack as the project
  grows. Walk through what is about to happen and why before doing it.
- **He merges every pull request himself.** Say explicitly, every time,
  when one is waiting on him — and when one must be **closed unmerged**
  (that happens: deliberately broken branches are sometimes used to prove
  a CI gate bites).
- **Put all the work in one push before announcing a PR is ready.**
  Squash-merging while a second push is in flight orphaned commits four
  times on 2026-11-17.
- **He runs every `az` command himself** in Azure Cloud Shell and pastes
  the output. There is no `az` and no Docker on his Mac.
- **Secrets never appear in chat.** Use `read -rsp "..." VAR; echo` on a
  line of its own, then check `${#VAR}`.
- Tick a checkbox only when the work is finished **and merged**.
- Write down what was *not* done, and what is unverified, as plainly as
  what was.

---

## 4. What is actually running, as of 2026-11-18

The app is deployed to Azure Container Apps staging and reachable on the
public internet. Nobody is using it yet.

| | state |
|---|---|
| hosting | single origin: FastAPI serves `/api` and the frontend |
| network | environment VNet-injected; PostgreSQL on a **private endpoint**, no public firewall rule |
| image | pulled from the project's own registry **as a managed identity** — no registry password anywhere |
| database URL | in **Key Vault**, read by that identity; the app's configuration holds only an address |
| database role | the app connects as the **runtime role**, which reads and writes data and is refused `CREATE TABLE` |
| TLS | `verify-full` — the server's certificate is checked |
| publishing | CI pushes to both registries through a **federated identity**, with no stored credential, behind an approval gate |

The schema is at migration `0037`, deployed.

**All fifteen High and Medium audit findings are fixed and deployed.**
Not merely merged — that distinction mattered: for two days thirteen
security commits sat merged and inert while the app served an older
image.

---

## 5. What was done, and where the evidence is

The two-day remediation followed
`docs/superpowers/plans/2026-11-15-security-remediation.md`. That plan is
also the record: each task carries an "applied" note saying what ran,
what was verified, what was deliberately **not** done, and what went
wrong on the way.

The operational half lives in `infra/azure/container-apps-app.md`, which
is the runbook: §1 migrations, §3 getting an image into the registry, §5
deployment, §9 credentials and rotation.

Three things in those documents are worth reading before touching Azure:

- **§9a** — how to check which database role the app is *actually* using,
  by asking `pg_stat_activity` rather than reading configuration.
- **§9b** — the rotation order, and why a revision restart is not enough.
- **§5c** — the Key Vault write path, including the role the operator has
  to take by name and hand back.

---

## 6. What is next, in order

### Four items close the audit (issue #196)

1. **Log ingestion posture.** The recorded position is "zero ingestion by
   design". This needs one paragraph recording it as an accepted risk, or
   a decision to change it. It gates the plan's Phase 0 sign-off.
2. **Burst-verify the connection pool.** It caps at 8 connections and has
   never been watched under load.
3. **Resource locks** on the shared resources. Honestly low value here —
   single operator, fictional data, automated backups — but cheap.
4. **The final verification pass**, which is the plan's own definition of
   done.

### Then the thing that matters more than any of them (issue #13)

**Test a backup restore.** Azure takes automated backups and nobody has
ever restored one.

Every fix of the last two days protects against somebody getting *in*.
None of them protects against losing the database with no way back. It is
cheap to test and it is the only item whose failure mode is
unrecoverable.

The rest of #13 is the pilot gate: 30 simultaneous players for 15
minutes, outage monitoring, agreed data-loss and restore targets, an
end-to-end exercise, and rollout/rollback documentation.

### Later (issue #84)

Managed identity for PostgreSQL, which removes the database password
rather than protecting it. A real piece of work — the app would refresh
an Entra token roughly hourly — and worth doing before real people use
the app.

---

## 7. Things that cost hours to learn

**A green check is not a verification.** The app answered 200 throughout
a period when it was connecting with the wrong credential. Check the
effect, not the exit code.

**There are two database passwords**, of different lengths. A length that
looks like a typo may be the right password for the wrong role.

**A placeholder in a command is an invitation.** `<user>` in a
vault-write command is how the administrator account ended up in the
app's secret. Spell roles out.

**Changing a Key Vault secret needs a new revision, not a restart.** A
restart left the old value in place while everything looked healthy.
`az containerapp update --revision-suffix <word>` re-reads everything.

**Azure Cloud Shell's home is ephemeral.** The clone and the virtualenv
are gone between sessions; step one is always rebuilding them.

**A federated identity's subject is read from a failed run, not
predicted.** A job with `environment:` presents `:environment:<name>`
instead of the branch ref, and some accounts fold numeric ids into the
names.

**`az role assignment delete` takes no `--assignee-principal-type`**;
only `create` does. Chain confirmations with `&&`, never `;`, or a failed
delete still prints "removed".

**No test suite can see a workflow.** Changing a command's contract means
searching `.github/` and the runbooks too, not just `backend/tests/`.

**The CI gates catch their own authors.** The Bicep lint failed the pull
request that introduced it, and again the next day on its author's own
change. That is the gates working.

---

## 8. Map of the documents

| path | what it is |
|---|---|
| `docs/superpowers/specs/2026-11-07-ranked-decision-record.md` | the settled rules; outranks any plan |
| `docs/superpowers/plans/2026-11-15-security-remediation.md` | the audit plan and its applied record |
| `infra/azure/container-apps-app.md` | the deployment and rotation runbook |
| `infra/azure/db-runtime-role.md` | the least-privilege database role |
| `infra/azure/runtime-identity.md`, `publish-identity.bicep` | the two managed identities |
| `infra/azure/README.md` | which template is the live deployable |

Real resource names are deliberately **not** in tracked documents — they
live in the private inventory. `backend/tests/test_docs_hygiene.py` fails
if one comes back.
