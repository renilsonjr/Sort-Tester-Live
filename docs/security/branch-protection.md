# Main-branch protection and PR checks

**Status:** Proposed protection settings; the workflow runs tests, but this document does not enable repository rules.

**Related:** [[2026-11-06-static-review]], [[2026-11-06-ranked-roadmap]].

## What the workflow checks

The Security regression workflow runs the existing three rendering regression checks on every pull request, every push to main, and manual dispatch. There are no path filters, so documentation-only pull requests receive the same check. Pull requests targeting a future Ranked integration branch are checked too.

The check is named **Security regression tests**. Keep that job name stable after selecting it as a required check. It tests normal scores, stored-score escaping, and name escaping. It is not a general vulnerability scanner, full browser test, or backend authorization test.

The workflow uses a read-only repository token, does not persist checkout credentials, and pins official actions to verified release commits. It installs Node.js 24 without dependency installation or package-manager caching. It contains no deployment steps and uses the ordinary pull_request event, not a privileged pull_request_target workflow. GitHub's own Pages deployment remains separate.

## Recommended setup order

1. Inspect the workflow PR and wait for Security regression tests to pass. Review the job log to confirm three tests passed.
2. Create an active branch ruleset targeting main. Public repository rulesets are supported on GitHub Free.
3. Require a pull request, block force pushes and branch deletion, and require review conversations to be resolved.
4. Use zero required approvals while the owner is the only collaborator. The owner can still inspect the diff and merge deliberately. An external approval requirement can be added when another reviewer is available.
5. Keep the bypass list empty so these rules also govern the owner's ordinary pushes and merges.
6. After the successful PR check is available, require Security regression tests from GitHub Actions. Prefer requiring the branch to be up to date before merging, so checks cover the latest main.
7. Merge through the PR flow. Confirm that the separate Pages deployment succeeds afterward.

Do not select Pages build/deploy as the required pre-merge test: the current Pages workflow runs after main changes. Do not require an invented check name that has never run. If a draft PR's workflow is awaiting approval, inspect it and approve its test run before expecting a check result.

Changing these settings is a separate repository administration action. This workflow PR does not apply them automatically. Administrators can edit the ruleset later; an empty bypass list protects the routine workflow, not against a deliberate administrative settings change.

## Verification

The same test command can be run locally:

```sh
node --test tests/security.test.mjs
```

When adding backend tests, extend the CI deliberately and decide whether to require a separate job. Keep the rendering check available on every PR so an unrelated change does not wait forever on a missing required status.

References: [GitHub ruleset rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets), [required-check troubleshooting](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks), [checkout release](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-node release](https://github.com/actions/setup-node/releases/tag/v7.1.0).
