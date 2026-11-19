"""Rule-logic tests for the offline infra policy checker (issue #205 item 3).

These exercise the invariants on crafted ARM fixtures: the reviewed baseline
must pass with no findings, and each representative unsafe mutation must raise
exactly the rule that guards it. The CI job additionally runs these same rules
over the ARM that `az bicep build` emits from the real templates, so the rules
are proven both on fixtures (here) and on the live compiled infrastructure.

Run from the repository root:
    python -m unittest infra.azure.policy.test_check
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import check  # noqa: E402  (path adjusted above so this works without packaging)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name: str) -> dict:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


def _rules(template: dict) -> set[str]:
    return {finding.rule for finding in check.evaluate(template)}


class BaselineFixture(unittest.TestCase):
    def test_reviewed_baseline_has_no_findings(self):
        self.assertEqual(check.evaluate(_load("baseline.arm.json")), [])


class UnsafeFixture(unittest.TestCase):
    def test_representative_unsafe_change_fails_on_every_rule(self):
        rules = _rules(_load("unsafe.arm.json"))
        self.assertEqual(
            rules,
            {
                "ingress-https-only",
                "image-digest-pinned",
                "no-plaintext-secret",
                "registry-admin-off",
                "registry-anon-pull-off",
                "keyvault-rbac",
                "keyvault-soft-delete",
                "no-broad-role",
                "oidc-issuer",
            },
        )

    def test_cli_exits_nonzero_for_unsafe_and_zero_for_baseline(self):
        self.assertEqual(check.main([os.path.join(FIXTURES, "baseline.arm.json")]), 0)
        self.assertEqual(check.main([os.path.join(FIXTURES, "unsafe.arm.json")]), 1)


class IndividualInvariants(unittest.TestCase):
    """Each invariant in isolation, so a single regression names one rule."""

    def _app(self, ingress=None, containers=None, secrets=None) -> dict:
        ingress = {"allowInsecure": False} if ingress is None else ingress
        containers = (
            [{"name": "c", "image": "r.io/app@sha256:" + "a" * 64}]
            if containers is None
            else containers
        )
        return {
            "resources": [
                {
                    "type": "Microsoft.App/containerApps",
                    "name": "app",
                    "properties": {
                        "configuration": {
                            "ingress": ingress,
                            **({"secrets": secrets} if secrets is not None else {}),
                        },
                        "template": {"containers": containers},
                    },
                }
            ]
        }

    def test_https_only_passes_and_fails(self):
        self.assertNotIn("ingress-https-only", _rules(self._app(ingress={"allowInsecure": False})))
        self.assertIn("ingress-https-only", _rules(self._app(ingress={"allowInsecure": True})))
        self.assertIn("ingress-https-only", _rules(self._app(ingress={"external": True})))

    def test_image_must_be_digest_pinned(self):
        self.assertNotIn(
            "image-digest-pinned",
            _rules(self._app(containers=[{"name": "c", "image": "r.io/app@sha256:" + "b" * 64}])),
        )
        self.assertIn(
            "image-digest-pinned",
            _rules(self._app(containers=[{"name": "c", "image": "r.io/app:v1"}])),
        )

    def test_image_as_format_expression_is_accepted(self):
        # The real app template compiles the image to a format() expression;
        # the digest still appears inside the string.
        image = "[format('{0}/{1}@sha256:{2}', parameters('r'), parameters('i'), parameters('s'))]"
        self.assertNotIn(
            "image-digest-pinned",
            _rules(self._app(containers=[{"name": "c", "image": image}])),
        )

    def test_inline_plaintext_secret_fails_but_references_pass(self):
        self.assertIn(
            "no-plaintext-secret",
            _rules(self._app(secrets=[{"name": "s", "value": "postgres://u:p@h/db"}])),
        )
        # A Key Vault reference or an ARM expression value is not a literal.
        self.assertNotIn(
            "no-plaintext-secret",
            _rules(self._app(secrets=[{"name": "s", "keyVaultUrl": "[parameters('u')]"}])),
        )
        self.assertNotIn(
            "no-plaintext-secret",
            _rules(self._app(secrets=[{"name": "s", "value": "[parameters('databaseUrl')]"}])),
        )
        self.assertNotIn(
            "no-plaintext-secret",
            _rules(self._app(secrets=[{"name": "s", "value": ""}])),
        )

    def test_registry_admin_and_anonymous_pull(self):
        def registry(admin, anon):
            return {
                "resources": [
                    {
                        "type": "Microsoft.ContainerRegistry/registries",
                        "name": "acr",
                        "properties": {"adminUserEnabled": admin, "anonymousPullEnabled": anon},
                    }
                ]
            }

        self.assertEqual(_rules(registry(False, False)), set())
        self.assertIn("registry-admin-off", _rules(registry(True, False)))
        self.assertIn("registry-anon-pull-off", _rules(registry(False, True)))

    def test_key_vault_rbac_and_soft_delete(self):
        def vault(rbac, soft):
            return {
                "resources": [
                    {
                        "type": "Microsoft.KeyVault/vaults",
                        "name": "kv",
                        "properties": {"enableRbacAuthorization": rbac, "enableSoftDelete": soft},
                    }
                ]
            }

        self.assertEqual(_rules(vault(True, True)), set())
        self.assertIn("keyvault-rbac", _rules(vault(False, True)))
        self.assertIn("keyvault-soft-delete", _rules(vault(True, False)))

    def test_broad_role_assignment_rejected(self):
        def assignment(guid):
            return {
                "resources": [
                    {
                        "type": "Microsoft.Authorization/roleAssignments",
                        "name": "ra",
                        "properties": {
                            "roleDefinitionId": f"[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '{guid}')]"
                        },
                    }
                ]
            }

        # AcrPull / Key Vault Secrets User are narrow and allowed.
        self.assertEqual(_rules(assignment("7f951dda-4ed3-4680-a7ca-43fe172d538d")), set())
        self.assertEqual(_rules(assignment("4633458b-17de-408a-b874-0445c86b69e6")), set())
        # Contributor / Owner are broad and rejected.
        self.assertIn("no-broad-role", _rules(assignment("b24988ac-6180-42a0-ab88-20f7382dd24c")))
        self.assertIn("no-broad-role", _rules(assignment("8e3af657-a8ff-443c-a75c-2fe8c4bcb635")))

    def test_federated_issuer_guarded(self):
        def federated(issuer):
            return {
                "resources": [
                    {
                        "type": "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials",
                        "name": "fic",
                        "properties": {"issuer": issuer},
                    }
                ]
            }

        self.assertEqual(_rules(federated(check.GITHUB_OIDC_ISSUER)), set())
        self.assertIn("oidc-issuer", _rules(federated("https://evil.example.com")))

    def test_nested_child_resources_are_reached(self):
        template = {
            "resources": [
                {
                    "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
                    "name": "id",
                    "resources": [
                        {
                            "type": "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials",
                            "name": "id/fic",
                            "properties": {"issuer": "https://evil.example.com"},
                        }
                    ],
                }
            ]
        }
        self.assertIn("oidc-issuer", _rules(template))


if __name__ == "__main__":
    unittest.main(verbosity=2)
