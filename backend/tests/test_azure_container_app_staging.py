"""Guard the narrow, fictional-data Container Apps staging deployment."""

import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "infra" / "azure" / "container-apps-staging.bicep"
PINNED_DIGEST = "0de6ceb356b0f82bb3dc6d3ddca263485675bd84cc3548251ef3ac01cf9baded"


class ContainerAppsStagingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text(encoding="utf-8")
        cls.code = re.sub(r"//.*$", "", cls.source, flags=re.MULTILINE)

    def test_exact_resource_boundary_and_names(self):
        resources = re.findall(r"^resource\s+\w+\s+'([^']+)'\s*=", self.code, re.MULTILINE)
        self.assertEqual(
            resources,
            [
                "Microsoft.App/managedEnvironments@2025-01-01",
                "Microsoft.App/containerApps@2025-01-01",
            ],
        )
        self.assertIn("name: 'cae-sort-api-stg'", self.code)
        self.assertIn("name: 'ca-sort-api-stg'", self.code)
        self.assertNotIn("Microsoft.DBforPostgreSQL", self.code)
        self.assertNotIn("Microsoft.Web", self.code)

    def test_region_tags_and_consumption_limits(self):
        self.assertIn("'northcentralus'", self.code)
        self.assertIn("workloadProfileType: 'Consumption'", self.code)
        self.assertIn("workloadProfileName: 'Consumption'", self.code)
        self.assertIn("cpu: json('0.25')", self.code)
        self.assertIn("memory: '0.5Gi'", self.code)
        self.assertIn("minReplicas: 0", self.code)
        self.assertIn("maxReplicas: 1", self.code)
        for key, value in {
            "project": "sort-tester-live",
            "environment": "staging",
            "data-classification": "fictional-only",
            "purpose": "api-only-container-apps-staging",
        }.items():
            self.assertIn(f"'{key}': '{value}'", self.code)
        self.assertIn("'expires-on': expiresOn", self.code)

    def test_https_health_and_no_secret_or_database_configuration(self):
        for fragment in (
            "external: true",
            "allowInsecure: false",
            "targetPort: 8000",
            "path: '/health'",
            "scheme: 'HTTP'",
        ):
            self.assertIn(fragment, self.code)
        for forbidden in ("secret", "password", "DATABASE_URL", "appLogsConfiguration", "registry", "Microsoft.Network"):
            self.assertNotIn(forbidden.lower(), self.code.lower())

    def test_only_reviewed_immutable_image_is_allowed(self):
        self.assertRegex(PINNED_DIGEST, r"^[0-9a-f]{64}$")
        self.assertIn("@allowed([", self.code)
        self.assertIn(f"'{PINNED_DIGEST}'", self.code)
        self.assertIn("@sha256:${imageSha256}", self.code)
        self.assertNotIn(":latest", self.code)


if __name__ == "__main__":
    unittest.main()
