"""The images CI runs, and the one the spike shipped (audit M-9, L4).

A tag is a name someone else can repoint. Three of them mattered here for
different reasons:

* the Postgres service image, where a moved tag means tests start failing
  with no commit to explain it;
* the Trivy scanner, which is handed the Docker socket and so runs with
  control of the daemon;
* the base images, already pinned before this task.

Dependabot does not update a service image or a `docker run` argument, so
these move only when a person moves them. That is the trade: a stale pin a
human can see beats a fresh one nobody chose.

The spike image is a separate point. It installed the development
requirements to serve one /health route, which is why it needed two pinned
upgrades to patch packages it never used.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP_IMAGE_WORKFLOW = ROOT / ".github" / "workflows" / "app-image.yml"
SPIKE_DOCKERFILE = ROOT / "infra" / "azure" / "spike.Dockerfile"
APP_DOCKERFILE = ROOT / "infra" / "azure" / "app.Dockerfile"
DOCKERIGNORE = ROOT / "infra" / "azure" / "app.Dockerfile.dockerignore"

# `name:tag` outside a comment, for the images we run rather than build.
TAGGED = re.compile(r"(?:image:\s*|docker run[^\n]*?\s)([a-z0-9./-]+):([\w.-]+)")


def _code(path: pathlib.Path) -> str:
    return "\n".join(
        line.split(" #")[0] if " #" in line else line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


class CiImagePinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = _code(APP_IMAGE_WORKFLOW)

    def test_the_database_service_image_is_pinned_by_digest(self):
        self.assertRegex(self.code, r"image:\s*postgres@sha256:[0-9a-f]{64}")
        self.assertNotRegex(self.code, r"image:\s*postgres:")

    def test_the_scanner_is_pinned_by_digest(self):
        # it gets /var/run/docker.sock, so this one runs with control of
        # the daemon that builds and holds our images
        self.assertRegex(self.code, r"aquasec/trivy@sha256:[0-9a-f]{64}")
        self.assertNotRegex(self.code, r"aquasec/trivy:")

    def test_no_image_in_this_workflow_is_named_by_tag(self):
        for name, tag in TAGGED.findall(self.code):
            self.fail(f"{name}:{tag} is named by tag; pin it by digest")

    def test_the_scan_still_blocks_on_high_and_critical(self):
        # pinning the scanner is worth nothing if the gate stops failing
        self.assertIn("--severity HIGH,CRITICAL", self.code)
        self.assertIn("--exit-code 1", self.code)


class SpikeImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SPIKE_DOCKERFILE.read_text(encoding="utf-8")
        cls.code = _code(SPIKE_DOCKERFILE)

    def test_it_installs_the_runtime_set_and_not_the_development_one(self):
        self.assertIn("COPY backend/requirements-runtime.txt", self.code)
        # the source copied, not the name it lands under inside the image
        self.assertNotIn("backend/requirements.txt", self.code)

    def test_the_patch_upgrades_are_gone_with_what_needed_them(self):
        # setuptools and msgpack were pinned to patch findings in packages
        # the spike never imported; they came with the development set
        for hack in ("setuptools==", "msgpack=="):
            self.assertNotIn(hack, self.code)

    def test_the_base_image_is_still_pinned(self):
        self.assertRegex(self.code, r"FROM python:[\d.]+-alpine@sha256:[0-9a-f]{64}")


class AppImageContentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ignore = DOCKERIGNORE.read_text(encoding="utf-8")
        cls.workflow = _code(APP_IMAGE_WORKFLOW)

    def test_the_development_manifest_does_not_ship(self):
        # `COPY backend` takes the whole directory, so an exclusion here is
        # the only thing keeping it out. Shipped, it is a printed list of
        # every package and version, handed to anyone who pulls the image.
        self.assertIn("backend/requirements.txt", self.ignore)
        self.assertIn("backend/tests", self.ignore)

    def test_ci_checks_that_it_really_is_absent(self):
        # the ignore file is the intention; this is the observation
        self.assertIn("/app/backend/requirements.txt", self.workflow)


if __name__ == "__main__":
    unittest.main()
