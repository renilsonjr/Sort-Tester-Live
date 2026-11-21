"""Who may publish the app image (audit M-7).

The image carries the Ranked question bank, and the package is private.
Publishing it is a manual dispatch, which anyone with write access to the
repository can start -- so without a gate, write access is publish access.

Task 8 puts two things in the way: the `publish` environment, whose
protection rules require the owner's approval and allow only two branches,
and a branch check inside the job itself.

The second one looks redundant and is not. The environment's rules are
repository *configuration*: an admin can widen them in the settings UI,
leaving no commit and no diff. The check in this file cannot be widened
without a change someone can review. These tests guard the half that lives
in the repository; the half that lives in GitHub's settings is verified by
running a dispatch, which the plan's Task 8 verification step covers.
"""
import pathlib
import re
import unittest

WORKFLOW = (
    pathlib.Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "app-image-publish.yml"
)

ALLOWED_REFS = ("refs/heads/main", "refs/heads/codex/ranked-mode")


class PublishGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        # comments explain the gate and name the refs; strip them so a
        # sentence about a rule can never stand in for the rule
        cls.code = "\n".join(
            line.split(" #")[0] if " #" in line else line
            for line in cls.source.splitlines()
            if not line.lstrip().startswith("#")
        )

    def test_the_publish_job_waits_for_an_environment(self):
        self.assertRegex(self.code, r"\n    environment: publish\b")

    def test_the_job_refuses_a_ref_outside_the_allowed_branches(self):
        for ref in ALLOWED_REFS:
            self.assertIn(ref.removeprefix("refs/heads/"), self.code)
        # the refusal is a failure, not a warning
        self.assertIn("is not allowed. Nothing was published.", self.code)
        self.assertRegex(self.code, r"\*\)[^\n]*exit 1")

    def test_the_branch_check_runs_before_anything_is_built_or_pushed(self):
        branch_check = self.code.index("Check the branch this run came from")
        for later in ("Build the image", "Log in to GHCR", "docker push"):
            self.assertLess(
                branch_check,
                self.code.index(later),
                f"the branch check must come before {later!r}",
            )

    def test_the_ref_reaches_the_shell_through_the_environment(self):
        # an expression spliced into the script text is how a branch name
        # becomes code; every other input here already goes through env
        self.assertIn("REF: ${{ github.ref }}", self.code)
        self.assertIn('case "$REF" in', self.code)

    def test_publishing_still_needs_the_typed_confirmation(self):
        # the gate is added to the existing checks, not instead of them
        self.assertIn('[ "$CONFIRM" = "publish" ]', self.code)
        self.assertIn("Require a passing App image run for this commit", self.code)


if __name__ == "__main__":
    unittest.main()


class RegistryPushTests(unittest.TestCase):
    """Publishing puts the image where the app pulls from (audit H-5 step 2).

    Until this, every deployment needed a person to copy the image across
    by hand, authenticating with a GitHub token that can read every
    private package the account can see. That token is the finding H-5
    closed for the running app; leaving it on the path that *puts* images
    in the registry would have closed the door and left the window.

    Nothing about this stores a credential. GitHub mints a token for the
    run, Azure checks it against a federated credential naming one
    repository and one branch, and answers with an access token that
    lives for minutes.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.code = "\n".join(
            line.split(" #")[0] if " #" in line else line
            for line in cls.text.splitlines()
            if not line.lstrip().startswith("#")
        )

    def test_the_run_can_mint_an_identity_token(self):
        self.assertIn("id-token: write", self.code)

    def test_azure_is_entered_without_a_stored_secret(self):
        self.assertIn("azure/login@", self.code)
        # client ids and tenant ids are identifiers, not secrets; a
        # password or a service-principal secret here would be the thing
        # this exists to avoid
        for stored in ("client-secret", "creds:", "AZURE_CREDENTIALS"):
            self.assertNotIn(stored, self.code)

    def test_the_login_action_is_pinned_to_a_commit(self):
        match = re.search(r"azure/login@([^\s#]+)", self.code)
        self.assertIsNotNone(match)
        self.assertRegex(match.group(1), r"^[0-9a-f]{40}$")

    def test_the_pushed_image_is_the_one_already_published(self):
        # a second build could produce a different digest for the same
        # commit, and then the two registries disagree about what that
        # commit means
        self.assertIn("docker tag", self.code)
        self.assertIn("steps.push.outputs.digest", self.code)
        self.assertNotRegex(
            self.code.split("Push the image to the Azure registry")[-1],
            r"docker build",
        )

    def test_the_digest_check_cannot_compare_ghcr_with_itself(self):
        # Once an image carries two names it has two RepoDigests, so
        # taking the first in the ACR step would be a check that always
        # passes. The GHCR step above may still do it: there the image
        # has exactly one name.
        acr_step = self.code.split("Push the image to the Azure registry")[-1]
        acr_step = acr_step.split("- name: Report the digest")[0]
        self.assertNotIn("index .RepoDigests 0", acr_step)
        self.assertIn("ACR_NAME.azurecr.io/", acr_step)
