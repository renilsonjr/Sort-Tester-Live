"""Real resource names and secret-bearing files stay out of the tree
(audit M-6, L3).

Two different problems, and they fail differently.

A parameters file carries the database URL with its password. Committed
once to a public repository it is leaked for good, and `git rm` does not
undo that. The defence is `.gitignore`, and this checks the ignore rules
actually match the shapes such a file takes rather than one name someone
remembered to list.

Resource names are not credentials. What they give away is reconnaissance:
which registry, which vault, which database server to probe -- and vault
and registry names resolve in global DNS. They belong in the private
inventory.

**These patterns match the shape of the names, never the names.** A guard
that listed the real values would be the leak it exists to prevent -- the
same way, earlier in this project, a sentence written to explain a
false positive became one.
"""
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Shapes, not values. Each is a real Azure naming convention used here:
# `<prefix><uniqueString(...)>` is 13 lowercase alphanumerics, and the
# database server carries a dated suffix.
FORBIDDEN_SHAPES = {
    "container registry name": re.compile(r"\bacrsortstg[a-z0-9]{10,}\b"),
    "key vault name": re.compile(r"\bkv-sortstg-[a-z0-9]{10,}\b"),
    "postgres server name": re.compile(r"\bpg-sort-tester-[a-z]+\d{4,}\b"),
    "subscription or principal GUID": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
    ),
    "container app ingress host": re.compile(r"\b[a-z]+-\d{8}\.[a-z]+\.azurecontainerapps\.io\b"),
}

# Where the project's own prose lives. Code and lock files are excluded:
# a GUID in a template is a role definition id, which is a public constant
# published by Microsoft, not a name of ours.
PROSE = ("*.md",)

ALLOWED = {
    # This file describes the shapes and must contain them.
    "backend/tests/test_docs_hygiene.py",
}

# Azure's built-in role definition IDs are the same GUID in every
# subscription on earth -- Microsoft publishes them. They say nothing
# about this project, and writing a role's ID beside its name is how a
# reader checks that a template grants what it claims to grant.
PUBLIC_AZURE_CONSTANTS = {
    "7f951dda-4ed3-4680-a7ca-43fe172d538d",  # AcrPull
    "4633458b-17de-408a-b874-0445c86b69e6",  # Key Vault Secrets User
}


def _tracked(patterns) -> list[pathlib.Path]:
    out = subprocess.run(
        ["git", "ls-files", "--", *patterns],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [ROOT / p for p in out]


class RealNamesStayOutOfProseTests(unittest.TestCase):
    def test_no_tracked_document_carries_a_real_resource_name(self):
        offenders = []
        for path in _tracked(PROSE):
            rel = path.relative_to(ROOT).as_posix()
            if rel in ALLOWED:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for label, shape in FORBIDDEN_SHAPES.items():
                for hit in shape.finditer(text):
                    if hit.group(0) in PUBLIC_AZURE_CONSTANTS:
                        continue
                    line = text.count("\n", 0, hit.start()) + 1
                    # the finding is reported by position and kind, not by
                    # quoting the value into a test log
                    offenders.append(f"{rel}:{line} carries a {label}")
        self.assertEqual(
            offenders,
            [],
            "real resource names belong in the private inventory:\n"
            + "\n".join(offenders),
        )


class ParameterFilesAreIgnoredTests(unittest.TestCase):
    """`git check-ignore` is the only authority on this.

    Reading `.gitignore` as text would only prove a line exists; this asks
    git what it would actually do with such a file.
    """

    CANDIDATES = (
        "infra/azure/app.parameters.local.json",
        "infra/azure/container-apps-app.parameters.json",
        "infra/azure/vault-params.json",
        "infra/azure/app-params.json",
    )

    def test_a_parameters_file_cannot_be_committed_by_accident(self):
        for name in self.CANDIDATES:
            with self.subTest(name=name):
                result = subprocess.run(
                    ["git", "check-ignore", "-q", name], cwd=ROOT
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"{name} is not ignored; one careless `git add` leaks a"
                    " database password into a public repository",
                )


if __name__ == "__main__":
    unittest.main()
