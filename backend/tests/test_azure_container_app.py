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
        # Names follow the environment, and the environment defaults to the
        # staging that already exists, so a deployment that says nothing
        # still names `cae-sort-app-stg` and `ca-sort-app-stg`.
        self.assertIn("name: 'cae-sort-app-${environmentSuffix}'", self.code)
        self.assertIn("name: 'ca-sort-app-${environmentSuffix}'", self.code)
        self.assertIn("param environmentSuffix string = 'stg'", self.code)
        self.assertIn("@allowed(['stg', 'pilot'])", self.code)

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
        # Always on unless a deployment asks otherwise, and never more than
        # one replica either way.
        self.assertIn("minReplicas: minReplicas", self.code)
        self.assertIn("param minReplicas int = 1", self.code)
        self.assertIn("@allowed([0, 1])", self.code)
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
        for line in (
            "project: 'sort-tester-live'",
            "environment: environmentTag",
            "'data-classification': dataClassification",
            "purpose: 'single-origin-app-container-apps'",
            # The defaults are what the live environment carries today.
            "var environmentTag = environmentSuffix == 'stg' ? 'production' : environmentSuffix",
            "param dataClassification string = 'employee-pilot'",
        ):
            self.assertIn(line, self.code)
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

    def test_the_app_signs_in_to_the_database_as_its_identity(self):
        # issue #84: no database password exists, so the template has none
        # to carry. The app fetches a token as the runtime identity.
        for fragment in (
            "name: 'SORT_TESTER_DB_AUTH'\n              value: 'managed_identity'",
            "name: 'SORT_TESTER_DB_IDENTITY_CLIENT_ID'",
            "value: runtimeIdentityClientId",
            "param runtimeIdentityClientId string",
        ):
            self.assertIn(fragment, self.code)

    def test_the_database_url_is_built_here_and_holds_no_password(self):
        # One fixed shape, written once: user@host, never user:password@host.
        # Read from the source: stripping `//` comments would cut the URL.
        self.assertIn(
            "var databaseUrl = 'postgresql://${runtimeIdentityName}@"
            "${databaseServerName}.postgres.database.azure.com:5432/${databaseName}"
            "?sslmode=verify-full&sslrootcert=system'",
            self.source,
        )
        self.assertEqual(self.source.count("postgresql://"), 1)
        self.assertNotRegex(self.source, r"postgresql://[^@'\s]*:[^@'\s]*@")
        # the role is named after the identity, so the user is derived from it
        self.assertIn(
            "var runtimeIdentityName = last(split(runtimeIdentityId, '/'))", self.code
        )
        self.assertIn(
            "name: 'SORT_TESTER_DATABASE_URL'\n              value: databaseUrl",
            self.code,
        )

    def test_certificate_checking_cannot_be_dropped_from_the_url(self):
        # #84: without sslrootcert=system libpq looks for a file the image
        # does not have and every connection fails.
        self.assertIn("sslmode=verify-full&sslrootcert=system", self.source)

    def test_the_old_password_path_is_gone(self):
        # the way back was removed by owner decision on 2026-11-20: the
        # database role it needs can no longer log in.
        for gone in (
            "@secure()",
            "secrets:",
            "secretRef",
            "keyVaultUrl",
            "databaseUrlSecretUri",
            "param databaseUrl",
            "database-url",
        ):
            self.assertNotIn(gone, self.code)

    def test_the_deletion_list_is_required(self):
        # issue #13: signing in as an identity, the app refuses to start
        # without the list. A parameter with no default makes forgetting it
        # a failed deployment instead of a crashed app.
        self.assertRegex(self.code, r"param deletionListUrl string\s*\n")
        self.assertNotRegex(self.code, r"param deletionListUrl string\s*=")
        self.assertIn(
            "name: 'SORT_TESTER_DELETION_LIST_URL'\n              value: deletionListUrl",
            self.code,
        )

    def test_a_bound_custom_domain_is_kept_by_a_deployment(self):
        # Seen on staging on 2026-11-20: a deployment whose ingress block
        # does not list the domain unbinds it. The what-if could not tell
        # that apart from its usual noise, so the template has to carry it.
        self.assertIn("param customDomainName string = ''", self.code)
        self.assertIn("param customDomainCertificateName string = ''", self.code)
        self.assertIn("customDomains: empty(customDomainName) ? [] : [", self.code)
        self.assertRegex(
            self.code,
            r"name: customDomainName\s*\n\s*bindingType: 'SniEnabled'\s*\n\s*"
            r"certificateId: '\$\{appEnvironment\.id\}/managedCertificates/"
            r"\$\{customDomainCertificateName\}'",
        )

    def test_the_certificate_is_referenced_never_created_here(self):
        # The first binding creates the certificate by command line, after
        # DNS is in place. A certificate resource here would try to issue
        # one before the domain can be validated.
        self.assertNotRegex(self.code, r"^resource\s+\w+\s+'[^']*managedCertificates")
        self.assertNotIn("Microsoft.App/managedEnvironments/managedCertificates@", self.code)

    def test_the_origin_to_configure_follows_the_custom_domain(self):
        # Only one address may write (backend/origin_guard.py). Printing
        # Azure's address while a custom domain is bound invites the wrong one.
        self.assertIn(
            "output appOriginToConfigure string = empty(customDomainName) ? ", self.source
        )
        self.assertIn(": 'https://${customDomainName}'", self.source)

    def test_the_image_is_pulled_by_identity_and_not_by_a_token(self):
        # audit H-5: the old GHCR token was account-scoped, so it could read
        # every private package the account can see, and it had to be typed
        # into a deployment to get there
        self.assertIn("identity: runtimeIdentityId", self.code)
        self.assertIn("type: 'UserAssigned'", self.code)
        for gone in ("registryUsername", "registryPassword", "registry-password"):
            self.assertNotIn(gone, self.code)

    def test_the_registry_host_must_be_given_not_defaulted(self):
        # a default would let a deployment keep pointing at the old public
        # registry without anyone choosing to
        self.assertRegex(self.code, r"param registryServer string\s*$|param registryServer string\n")
        self.assertNotRegex(self.code, r"param registryServer string\s*=")

    def test_the_image_path_has_no_github_account_prefix(self):
        # the image used to live at ghcr.io/<account>/<name>, and that
        # account prefix is GHCR's own namespacing. `az acr import` puts it
        # at <name> in our registry, so carrying the prefix over points the
        # deployment at a repository that does not exist.
        self.assertRegex(
            self.code, r"param imageRepository string = 'sort-tester-live-app'"
        )
        self.assertNotIn("renilsonjr/sort-tester-live-app", self.code)

    def test_the_session_cookie_is_marked_secure(self):
        self.assertIn("SORT_TESTER_COOKIE_SECURE", self.code)
        self.assertRegex(self.code, r"'SORT_TESTER_COOKIE_SECURE'\s*\n\s*value: 'true'")

    def test_the_public_origin_can_be_configured_and_is_reported(self):
        self.assertIn("SORT_TESTER_APP_ORIGIN", self.code)
        self.assertIn("param appOrigin string = ''", self.code)
        self.assertIn("output appOriginToConfigure string", self.code)

    def test_azure_ingress_trust_cannot_be_disabled_or_overcounted(self):
        # This Azure-only template has one verified ingress hop (#78).
        # An empty default groups unrelated clients; 2 trusts client input.
        self.assertRegex(
            self.code,
            r"@allowed\(\[\s*'1'\s*\]\)\s*param trustedProxies string = '1'",
        )
        self.assertRegex(self.code, r"'SORT_TEST_TRUST_PROXY'\s*\n\s*value: trustedProxies")


if __name__ == "__main__":
    unittest.main()
