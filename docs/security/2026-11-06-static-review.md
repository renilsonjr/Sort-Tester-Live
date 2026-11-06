# Static app security review — November 6, 2026

**Scope:** `renilsonjr/Sort-Tester-Live`, main at `70b62bd`, its 17 main-branch commits, the browser application, external spreadsheet dependency, and selected GitHub/Pages settings. This branch prepares limited hardening; it does not deploy it.

**Related:** [[2026-11-06-ranked-pilot-design]], [[2026-11-06-ranked-roadmap]].

This is a scoped source/configuration review, not a penetration test or evidence that compromise is impossible. No real employee log was read or uploaded, and no disruptive requests were made to the live website.

## Trust boundaries

The current application has no backend, authentication, database, or employee API. The repository, questions, answers, study routes, and planning files are public. Browser input and saved local log values must be treated as untrusted. Third-party scripts execute with the page's browser privileges. GitHub Pages serves the root of main, so merging a main-branch change publishes it.

## Findings and prepared fixes

| Finding | Current impact | Prepared action |
| --- | --- | --- |
| No `.gitignore` | Future local credentials, environments, databases, and employee exports could be accidentally committed | Add ignore rules and check representative paths; retain sanitized environment templates |
| Saved score values inserted into HTML without escaping | Prior access to write same-origin browser storage could cause stored markup to be interpreted; normal name input is escaped, and no direct remote write path was identified | Escape both stored score fields and add a renderer regression check using passive markup |
| Spreadsheet script pinned to 0.18.5 with no integrity check | Old dependency with published advisories; changing CDN bytes were not checked by the browser | Move to the upstream-documented 0.20.3 URL, pin its SHA-384 integrity, and require anonymous CORS |

The score change is a narrow defense: it does not validate the complete local-log schema. Malformed log records can still break the log view, and a user with control of their own browser can still alter Practice scores. Those local scores are not a trustworthy future competitive record.

### Spreadsheet advisory reachability

[CVE-2023-30533](https://github.com/advisories/GHSA-4r6h-8v6p-xvw6) affects reading crafted workbooks before 0.19.3; its advisory explicitly states export-only workflows are unaffected. [CVE-2024-22363](https://github.com/advisories/GHSA-5pgg-2g8v-p4x9) affects versions before 0.20.2. This app generates workbooks and has no workbook-upload/import path. The older version is a dependency hygiene finding, not proof of a remotely exploitable import vulnerability here.

The [upstream browser installation guide](https://docs.sheetjs.com/docs/getting-started/installation/standalone/) identifies 0.20.3 as its current standalone release. The new integrity hash was computed from that version's HTTPS response, and its CORS header was checked. [Subresource integrity](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Subresource_Integrity) detects a changed resource; it does not prove the original library is trustworthy. An external CDN is still an availability dependency.

## Verified checks

- Gitleaks default-rule scan of all 17 main-branch commits: no detected secrets. A separate worktree scan also found none. These heuristic scans cannot prove that no sensitive information exists.
- GitHub secret scanning and push protection: enabled; the secret-alert API returned an empty list at review time.
- Pages HTTPS enforcement: enabled. A live response returned HTTPS and an HSTS header.
- Names and study search values are escaped on inspected HTML paths; search output is rendered from known chart rows. No runtime `eval`, dynamic code constructor, file upload, or application API was found in first-party app code.
- A passive stored-score markup test failed before the fix and passed afterward. The focused suite has three checks: normal score rendering, stored score escaping, and name escaping.
- The actual new library and app workbook builder produced populated and empty XLSX files. Both contained Results and Missorts sheets; an equals-prefixed name remained text rather than a formula.
- Ignore checks covered nested environments/configuration, local databases, backups, and employee XLSX exports. Source files and sanitized environment templates remain trackable.

## Remaining limits and follow-up

- **Public data is public:** `.gitignore` is a version-control aid, not access control. It does not remove tracked content or history. If practice routes need employee-only access, the current public Pages design does not enforce that requirement. See [Git ignore behavior](https://git-scm.com/docs/gitignore).
- **Shared-device privacy:** names and results stay in browser local storage without encryption or per-employee isolation. Another person using that browser profile can view them. Clear the log on shared devices and use optional identifiers deliberately. Do not put future passwords or database credentials there.
- **Local data validation:** add schema checks and graceful recovery for malformed log records as part of broader regression work; do not infer trustworthy employee performance from client-side Practice storage.
- **Browser policy:** no Content Security Policy was observed in the live main-page response or HTML. Consider a restrictive policy and framing controls when reviewing the hosting design; current inline styles and previews need deliberate compatibility work.
- **Repository protections:** main reported `protected: false`, and the repository ruleset list was empty. Choose a PR/check policy before a larger contributor or employee rollout. Direct main pushes are especially consequential because they publish the site.
- **Dependency monitoring:** Dependabot alerts/updates were disabled. A script loaded directly from a CDN is not covered by an absent npm lockfile. Track upstream updates deliberately; enabling alerts alone will not monitor this script tag.
- **Uninspected settings:** the GitHub Actions permissions endpoint required an unavailable CLI token scope; no conclusion about those permissions is made. The current repository has no tracked workflows.
- **Future backend:** authentication, ownership checks, password/session handling, server deadlines, once-only score settlement, CORS, private PostgreSQL, and backup recovery still need implementation and review in their owning roadmap issues.

Recheck the deployed site after merging this hardening branch. Review server security again when an actual backend exists.
