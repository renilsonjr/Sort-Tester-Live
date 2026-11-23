# Rollout runbook — issue #13, rollout documents

How a change reaches players, how to take it back, how the owner launches
the official season, and how the three hats become final. Written on
2026-11-22 from what was actually done that week; each section says what
has been done on the live environment and what has only been rehearsed on
a local database.

The app is one container on Azure Container Apps (`ca-sort-app-stg` in
`rg-sort-tester-staging`) serving the site and `/api` at
<https://sortquiz.app>. GitHub Pages is off and never hosted the API.
There is one environment, and it holds real accounts: nothing here is
rehearsed on it first.

Related runbooks: `container-apps-app.md` (building the environment,
migrations, credentials) and `restore-runbook.md` (database restore).

## Who does what

- The owner merges every pull request, approves every image publish and
  runs every `az` command, in Cloud Shell.
- Nobody signs in to the live site to test. A deploy is checked from the
  files the site serves.

## 1. Ship a change (image only)

Use this path only when the change carries **no new migration and no new
`SORT_TESTER_` setting** since the commit that is live. Check before
starting, with the live commit from the last deploy:

```bash
git fetch origin
git diff --name-only <live-commit> origin/codex/ranked-mode -- backend/migrations/versions/
```

An empty answer means no migration. A change with a migration follows
`container-apps-app.md` §1d and §1d-i instead (open the database, migrate,
grant new tables to the app role, close it), before the image is swapped.

1. **Work pull request → `codex/ranked-mode`, merged with Squash.**
2. **Pull request `codex/ranked-mode` → `main`, merged with "Create a
   merge commit".** It carries everything `main` does not have yet; its
   Commits tab is the list of what will ship. Squash here makes the two
   branches diverge. Merging deploys nothing.
3. **Confirm `main` has everything.** This must print nothing:

   ```bash
   git fetch origin && git log --oneline origin/main..origin/codex/ranked-mode
   ```

4. **Publish the image from `main`.** The workflow refuses any other
   branch.

   ```bash
   gh workflow run app-image-publish.yml --ref main -f confirm_publish=publish -f expected_visibility=private
   ```

   The run waits for the owner: Review deployments → `publish` → Approve
   and deploy. When it succeeds, the image digest is in its log as
   `imageSha256=<64 hex characters>`.

5. **Read what is live. This is the rollback; write it down.**

   ```bash
   az containerapp show -g rg-sort-tester-staging -n ca-sort-app-stg --query "{revision:properties.latestRevisionName, ready:properties.latestReadyRevisionName, image:properties.template.containers[0].image}" -o jsonc
   ```

6. **Swap the image.** This changes the live app.

   ```bash
   az containerapp update -g rg-sort-tester-staging -n ca-sort-app-stg --image <acr-name>.azurecr.io/sort-tester-live-app@sha256:<digest> --revision-suffix <short-word> --query "{revision:properties.latestRevisionName, image:properties.template.containers[0].image, state:properties.provisioningState}" -o jsonc
   ```

   `<acr-name>` is the registry in the image line that step 5 printed;
   real resource names are kept out of this repository on purpose. The
   swap keeps every setting, secret reference, identity, the custom
   domain and its certificate. Expect `Succeeded`.

7. **Check from the served files, without signing in.** For each file the
   change touched under `src/`:

   ```bash
   curl -s "https://sortquiz.app/src/app.js?check=$RANDOM" | cmp - <(git show origin/main:src/app.js) && echo SAME
   ```

   The old revision goes on answering for 20 to 30 seconds after the swap,
   so a first "differ" is normal: try again. Then `https://sortquiz.app/`
   and `/health` must answer 200. `/health` does not touch the database,
   so it says nothing about the database.

   A change to server code only has no served file to compare. Compare
   one anyway to prove the image, and rely on the tests for the rest.

### What players feel during a swap

- A player in the middle of a quiz keeps playing if the gap is shorter
  than 18 seconds (3 of loss plus 15 of grace). The question on screen
  during the gap can time out: question deadlines do not move.
- Since PR #300, an attempt cut off by the restart is voided with no score
  and the player may start again. A player who dropped by themselves in
  the last seconds before the swap is voided too.
- Do not swap during a tie-break window unless it cannot wait: an
  interrupted round restarts for all its players.

Done on the live environment: several times on 2026-11-21 and
2026-11-22, the last two as revisions `es1` and `tie1`. The behaviour of
PR #300 through a real swap has not been observed yet.

## 2. Roll back

Rolling back is the same swap, with the image written down in step 5:

```bash
az containerapp update -g rg-sort-tester-staging -n ca-sort-app-stg --image <acr-name>.azurecr.io/sort-tester-live-app@sha256:<previous-digest> --revision-suffix <short-word>
```

Then check as in step 7, against the commit that image was built from.

**Which digest?** [[releases]] records every deploy with the migration it
needs. Walk up from the live row while the migration number stays the same;
the last such row is the oldest image that can still serve this database.

**Not a traffic split.** The app runs in single-revision mode, so
`az containerapp ingress traffic set --revision-weight ...` is refused. A
rollback is the deploy above, pointed at an older digest.

Limits:

- **This rolls back code, not data.** Points settled, accounts created
  and deletions made while the newer code ran all stay.
- **Only across image-only deploys.** If a migration ran in between, the
  older code may not match the database: do not swap back. Fix forward,
  or restore the database (`restore-runbook.md`), which also undoes
  everything players did since the restore point.
- `main` is not rewritten. To take a change out for good, revert it in a
  pull request and ship that the normal way.

Done on the live environment: never needed. The command is the one used
for every deploy, pointed at an older digest.

## 3. Launch the official season

The launch happens once and cannot be undone. It:

- ends every unfinished Pre-Season attempt with no score;
- sets **every balance to 0**; badges follow, so everyone is Iron;
- keeps the Pre-Season history;
- opens the official season, which ends on the date given, by default
  2026-12-31 at 11:59 p.m. Eastern.

There is no launch button in the site. The launch is one request made by
the owner's own signed-in browser.

### Before

- [ ] The owner has decided the launch moment and the end.
- [ ] Players were told that Pre-Season points go back to 0.
- [ ] No test or fictional account is on the Pre-Season leaderboard.
- [ ] Prize eligibility is up to date (Settings → Owner tools → Prize
      eligibility). Approvals carry over the launch. They can still be
      added while the official season is open, and never after it ends.
- [ ] Note the time, as the restore point just before the launch
      (`restore-runbook.md`). A restore to before the launch also undoes
      the launch and everything after it.
- [ ] Nobody is expected to be mid-quiz: an unfinished attempt is ended
      with no score.

### The launch

1. Sign in at <https://sortquiz.app> as the owner.
2. Open the browser's developer console on that page (Chrome on a
   computer: View → Developer → JavaScript Console).
3. Paste the block below, change the label if wanted, and press Enter. It
   asks for the owner's login ID in a box, so the ID is never part of the
   command. It then asks for a last confirmation that states what will
   happen.

```js
(async () => {
  const label = 'Season 1';
  const closesAt = null; // null = 2026-12-31 11:59 p.m. Eastern; or e.g. '2026-12-31T23:59:00-05:00'
  const post = (path, body) => fetch(path, {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const loginId = prompt('Owner login ID (confirms it is you):');
  if (!loginId) return console.log('Stopped. Nothing was changed.');
  const sure = await post('/api/auth/reauthenticate', { login_id: loginId });
  if (sure.status !== 204) return console.log('Login ID not accepted (' + sure.status + '). Nothing was changed.');
  if (!confirm('Launch "' + label + '" now? Every balance goes to 0 and unfinished attempts end with no score. This cannot be undone.')) {
    return console.log('Stopped. Nothing was changed.');
  }
  const body = { label, confirm: 'LAUNCH' };
  if (closesAt) body.closes_at = closesAt;
  const launched = await post('/api/ranked/season/launch', body);
  console.log(launched.status, await launched.text());
})();
```

What the last line prints:

| Printed | Meaning |
|---|---|
| `Stopped. Nothing was changed.` | The login ID box was left empty, or the last confirmation was refused. |
| `Login ID not accepted (403). Nothing was changed.` | The login ID typed is not this account's. Several wrong tries are rate-limited (`429`). |
| `201` and the season with its `closes_at` | Launched. `2027-01-01T04:59:00+00:00` is 2026-12-31 at 11:59 p.m. Eastern. |
| `409 Already launched` | It had already been launched. Nothing changed now. |
| `428` | The login ID confirmation is missing or older than five minutes. Run the block again. |
| `422` with a sentence | The request was refused and nothing changed: no label, an end time in the past or with no time zone, or a label already used. |
| `403 {"detail":"Forbidden"}` | This account is not the owner. Nothing changed. |
| A server error, or no answer | Run the block again. An interrupted launch is completed by running it again; balances are reset only in the same step that creates the official season. |

### After

- [ ] Home shows "The official season has started" with the start and end
      dates.
- [ ] Ranked shows the season name and "Closes".
- [ ] The leaderboard is empty until somebody approved completes a quiz.
- [ ] The owner's own points read 0; Profile → history still lists
      Pre-Season attempts.

Done on the live environment: never. Rehearsed on a local database on
2026-11-21 and 2026-11-22 through the route. The console block itself was
run in a browser against a local server on 2026-11-22, with the two boxes
answered by script: every line of the table except the server error was
seen, both balances went to 0 and the one unfinished attempt ended as
`launch_reset`. A real browser console and real dialog boxes were not
used.

## 4. Season end and the three hats

Nothing needs to be pressed at the end. The app has no background timer:
each step below happens on the first request any signed-in player makes
after its time has come. If nobody opens the app, open it.

1. **End time.** No new quiz can start. A quiz already started has five
   more minutes. New prize approvals are refused from here on; an approval
   can still be withdrawn.
2. **Five minutes later: the freeze.** Unfinished attempts are ended with
   what they had scored and no penalty. Points are final. Ranked reads
   "Points are final for this season."
3. **A tie for a hat opens a tie-break by itself**, when more players than
   hats share the points at the cut. Each tied player sees it on Home and
   on Ranked. Round 1 closes 24 hours after the scheduled end; a later
   round closes 24 hours after it opened. A round is closed by the first
   request after its deadline.
4. **Some ties come to the owner** (Settings → Owner tools → Prize
   selection): still tied after the last round (3 rounds for Challenger,
   5 below), no unused Hard questions left, or several players who did not
   finish competing for fewer hats. Choosing asks for the login ID and is
   final.
5. **Final.** When nothing is pending the three winners are written once.
   The leaderboard reads "Final results. The three hats are decided." and
   the winners carry the crown.

### What the owner does

- [ ] After the end time plus five minutes, open the app and read Ranked
      and the leaderboard.
- [ ] If Owner tools shows ties waiting, settle them.
- [ ] While a tie-break window is open, avoid deploys: an interrupted
      round restarts for everyone in it.
- [ ] When the board says final, **write down the three winners at once**:
      username, tag, and the roster reference from Prize eligibility. The
      app keeps no other record: if a winner deletes their account
      afterwards, their row leaves the board.
- [ ] Hand over the hats.

Fewer than three winners is possible and correct: only approved players
with one completed Ranked quiz in the season are ranked.

Done on the live environment: never. Rehearsed on local databases on
2026-11-21 and 2026-11-22 (issue #13, box 7 records), with season ends and
round deadlines moved by hand in most runs; one run waited the real five
minutes.

## 5. Public rollout authorization

Two separate owner decisions, and neither is implied by any merge, publish
or deploy in this file.

**The app is open to its public, the employees.** Authorized by the owner
on **2026-11-22**. This covers what already runs at the app's address:
accounts, Practice and Ranked in Pre-Season. In the owner's words, the
public here is the employees, and this is not the official season.

**The official season has not been launched.** Launch moment chosen:
**not yet**. The launch resets every balance and opens the competition for
the hats; it is tracked in issue #258 and done with section 3 of this file.

State of issue #13 when the authorization was given: the outage item
(box 3) and the 30-player load item (box 5) were ticked on the owner's
decision with their limits written beside them (no correction for an
outage without a restart; about 13 to 16 simultaneous players within the
1-second target on the current replica). Still open: the note-expiry
observation of box 4.
