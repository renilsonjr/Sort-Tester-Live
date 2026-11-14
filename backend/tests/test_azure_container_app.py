"""Guard the single-origin app deployment template (issue #41).

Azure is never contacted here. These read the template as text, the same
way `test_azure_container_app_staging.py` guards the API-only one, so the
boundaries hold even on a machine with no Azure CLI.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "infra" / "azure" / "container-apps-app.bicep"


class SingleOriginAppTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text(encoding="utf-8")
        cls.code = re.sub(r"//.*$", "", cls.source, flags=re.MULTILINE)

    def test_creates_only_the_environment_and_the_app(self):
        resources = re.findall(r"^resource\s+\w+\s+'([^']+)'\s*=", self.code, re.MULTILINE)
        self.assertEqual(
            resources,
            [
                "Microsoft.App/managedEnvironments@2025-01-01",
                "Microsoft.App/containerApps@2025-01-01",
            ],
        )
        self.assertIn("name: 'cae-sort-app-stg'", self.code)
        self.assertIn("name: 'ca-sort-app-stg'", self.code)

    def test_creates_no_database_network_or_monitoring_resource(self):
        for forbidden in (
            "Microsoft.DBforPostgreSQL",
            "Microsoft.Web",
            "Microsoft.Network",
            "Microsoft.OperationalInsights",
            "Microsoft.Insights",
            "appLogsConfiguration",
        ):
            self.assertNotIn(forbidden, self.code)

    def test_does_not_collide_with_the_api_only_staging_names(self):
        for existing in ("cae-sort-api-stg", "ca-sort-api-stg"):
            self.assertNotIn(existing, self.code)

    def test_exactly_one_always_on_replica(self):
        self.assertIn("minReplicas: 1", self.code)
        self.assertIn("maxReplicas: 1", self.code)
        # More than one replica would split the in-memory sign-up limiter.
        self.assertNotIn("minReplicas: 0", self.code)
        # No autoscale rule may raise the ceiling.
        self.assertNotIn("concurrentRequests", self.code)

    def test_region_size_and_tags_match_the_cost_estimate(self):
        self.assertIn("'northcentralus'", self.code)
        self.assertIn("workloadProfileType: 'Consumption'", self.code)
        self.assertIn("workloadProfileName: 'Consumption'", self.code)
        self.assertIn("cpu: json('0.25')", self.code)
        self.assertIn("memory: '0.5Gi'", self.code)
        for key, value in {
            "project": "sort-tester-live",
            "environment": "staging",
            "data-classification": "fictional-only",
            "purpose": "single-origin-app-container-apps",
        }.items():
            self.assertIn(f"'{key}': '{value}'", self.code)
        self.assertIn("'expires-on': expiresOn", self.code)

    def test_https_only_ingress_with_a_health_probe(self):
        for fragment in (
            "external: true",
            "allowInsecure: false",
            "targetPort: 8000",
            "path: '/health'",
        ):
            self.assertIn(fragment, self.code)

    def test_image_is_pinned_by_digest_and_never_by_tag(self):
        self.assertIn("@sha256:${imageSha256}", self.code)
        self.assertIn("@minLength(64)", self.code)
        self.assertIn("@maxLength(64)", self.code)
        # A digest parameter with a default would let a stale image slip in.
        self.assertRegex(self.code, r"param imageSha256 string\s*$|param imageSha256 string\n")
        self.assertNotRegex(self.code, r"param imageSha256 string\s*=")
        self.assertNotRegex(self.code, r"image:\s*'[^']*:latest'")

    def test_secrets_are_secure_parameters_never_literals(self):
        for name in ("registryPassword", "databaseUrl"):
            self.assertRegex(self.code, rf"@secure\(\)\s*\nparam {name} string")
        # Secrets reach the container by reference, not as plain values.
        self.assertIn("secretRef: 'database-url'", self.code)
        self.assertIn("passwordSecretRef: 'registry-password'", self.code)
        self.assertNotIn("postgresql://", self.code)

    def test_the_session_cookie_is_marked_secure(self):
        self.assertIn("SORT_TESTER_COOKIE_SECURE", self.code)
        self.assertRegex(self.code, r"'SORT_TESTER_COOKIE_SECURE'\s*\n\s*value: 'true'")

    def test_the_public_origin_can_be_configured_and_is_reported(self):
        self.assertIn("SORT_TESTER_APP_ORIGIN", self.code)
        self.assertIn("param appOrigin string = ''", self.code)
        self.assertIn("output appOriginToConfigure string", self.code)

    def test_proxy_trust_is_off_unless_explicitly_set(self):
        self.assertIn("SORT_TEST_TRUST_PROXY", self.code)
        self.assertIn("param trustedProxies string = ''", self.code)
        self.assertRegex(self.code, r"'SORT_TEST_TRUST_PROXY'\s*\n\s*value: trustedProxies")


if __name__ == "__main__":
    unittest.main()
