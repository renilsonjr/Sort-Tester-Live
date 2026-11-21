"""The three security gates, and the pins that make them mean something
(audit M-8).

Each gate answers a different question -- was a secret committed, does this
pull request add a vulnerable dependency, do the dependencies we already
have carry a known vulnerability -- and each fails differently when it is
wrong. The tests here guard the ways a gate can keep reporting success
while checking nothing:

* an action pinned to a tag, which its owner can move to other code;
* a shallow checkout, which leaves gitleaks almost no history to read;
* `continue-on-error` on the runtime audit, which turns a finding in
  production into a green tick.

They cannot test that the gates *find* anything -- that is what the
verification run on the opening pull request is for.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "security-gates.yml"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"

PINNED_SHA = re.compile(r"uses:\s*([^\s@]+)@([^\s#]+)")


class SecurityGatesWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        # A comment explaining a flag is not the flag. Assertions about
        # what the workflow *does* read this; assertions about pins and
        # structure may use the source.
        cls.code = "\n".join(
            line for line in cls.source.splitlines()
            if not line.lstrip().startswith("#")
        )

    def test_every_third_party_action_is_pinned_to_a_commit(self):
        uses = PINNED_SHA.findall(self.source)
        self.assertGreaterEqual(len(uses), 3, "expected several actions here")
        for action, ref in uses:
            self.assertRegex(
                ref,
                r"^[0-9a-f]{40}$",
                f"{action} is pinned to {ref!r}, which is not a commit SHA. "
                "A tag can be moved to different code by whoever owns it.",
            )

    def test_the_change_scan_has_a_range_to_work_with(self):
        # a shallow clone is the default, and the action cannot resolve
        # the commit range it scans without the full fetch. This does NOT
        # make it scan the history: the first run of this workflow
        # reported "1 commits scanned" on a pull request, which is why
        # there is a second job below.
        self.assertIn("fetch-depth: 0", self.source)
        self.assertIn("gitleaks/gitleaks-action@", self.source)

    def test_something_actually_scans_the_whole_history(self):
        # the per-change scan finds a secret being added; only this finds
        # one that is already in here, which is the question that matters
        # after a key leaks
        self.assertIn("secrets-history:", self.code)
        history = self.code.index("secrets-history:")
        job = self.code[history:self.code.index("dependencies:", history)]
        # no --log-opts: a range would make it a per-change scan again
        self.assertIn("gitleaks detect", job)
        self.assertNotIn("--log-opts", job)
        self.assertIn("--exit-code 1", job)

    def test_the_downloaded_binary_is_checked_against_a_digest(self):
        # a binary fetched at run time is a supply chain of its own; a
        # version alone would let a moved release through
        self.assertRegex(self.source, r"GITLEAKS_SHA256: [0-9a-f]{64}")
        self.assertIn("sha256sum --check", self.source)
        self.assertIn("--proto '=https'", self.source)

    def test_the_runtime_audit_cannot_be_made_advisory(self):
        runtime = self.source.index("Audit the runtime dependencies")
        dev = self.source.index("Audit the development dependencies")
        between = self.source[runtime:dev]
        self.assertNotIn(
            "continue-on-error",
            between,
            "a finding in the runtime set is a finding in production",
        )
        self.assertIn("requirements-runtime.txt", between)

    def test_the_audit_runs_on_a_schedule_and_not_only_on_changes(self):
        # a dependency that was clean when it was added does not stay
        # clean, and no push would ever notice
        self.assertIn("schedule:", self.source)
        self.assertRegex(self.source, r"cron:\s*'[^']+'")

    def test_the_workflow_asks_for_no_more_than_read_access(self):
        self.assertRegex(self.source, r"permissions:\s*\n\s*contents: read")
        for wider in ("packages: write", "contents: write", "id-token: write"):
            self.assertNotIn(wider, self.source)


class GitleaksConfigTests(unittest.TestCase):
    """What we told the scanner to ignore, and how narrowly.

    Every exception here is a place the scanner has been told to stay
    quiet. The danger is not the exception itself but its width: an
    allowlist over a directory silences a whole area, and test directories
    are exactly where a real key gets pasted "just for a moment".
    """

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")

    def test_it_extends_the_default_rules_instead_of_replacing_them(self):
        self.assertIn("useDefault = true", self.source)

    def test_no_allowlist_covers_a_whole_directory(self):
        # a path pattern that ends at a directory, rather than a file,
        # silences everything written there later as well
        for line in self.source.splitlines():
            if "paths" not in line:
                continue
            self.assertIn(
                r"\.py",
                line,
                f"allowlist path is not a single file: {line.strip()!r}",
            )

    def test_each_exception_is_tied_to_a_shape_and_not_just_a_file(self):
        # a file-only allowlist would let a real key pasted into that same
        # file through
        self.assertIn("regexes", self.source)


class DependabotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = DEPENDABOT.read_text(encoding="utf-8")

    def test_it_watches_both_the_app_and_the_actions(self):
        self.assertIn("package-ecosystem: pip", self.source)
        self.assertIn("package-ecosystem: github-actions", self.source)

    def test_the_actions_ecosystem_is_what_keeps_the_sha_pins_current(self):
        # pinning to a SHA means nothing else updates them; without this
        # they age into unpatched versions while looking deliberate
        actions = self.source.index("package-ecosystem: github-actions")
        self.assertIn("interval: weekly", self.source[actions:])


if __name__ == "__main__":
    unittest.main()


class BicepLintTests(unittest.TestCase):
    """Templates are compiled on every change, not at deployment time.

    A template that does not compile used to be found by whoever deployed
    it -- mid-change, often inside a booked window. This morning's own
    §5c step 1 was exactly that: compiling by hand, from Cloud Shell,
    hoping.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        cls.code = "\n".join(
            line for line in cls.source.splitlines()
            if not line.lstrip().startswith("#")
        )

    def test_the_templates_job_exists(self):
        self.assertIn("templates:", self.code)
        self.assertIn("az bicep build", self.code)

    def test_it_finds_templates_by_glob_and_not_by_a_list(self):
        # a listed file is one someone has to remember to add; two
        # templates were written today and neither would have been in a
        # list written yesterday
        self.assertIn("infra/azure/*.bicep", self.code)

    def test_an_empty_match_is_a_failure_not_a_pass(self):
        # a glob that matches nothing would otherwise make this job green
        # while compiling nothing at all
        self.assertIn("No templates found", self.source)

    def test_a_warning_is_treated_as_a_failure(self):
        # bicep's linter reports warnings without failing the build, so a
        # job that only checked the exit code would ignore every one
        self.assertRegex(self.code, r'grep -qiE "warning\|error"')

    def test_every_template_in_the_repository_would_be_compiled(self):
        # the guard above says the job globs; this says the glob covers
        # where the templates actually are
        import pathlib

        found = sorted(
            p.as_posix()
            for p in (ROOT / "infra" / "azure").glob("*.bicep")
        )
        self.assertTrue(found, "no templates found in infra/azure")
        for path in found:
            self.assertTrue(path.endswith(".bicep"))
