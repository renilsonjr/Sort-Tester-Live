import re
from pathlib import Path
import unittest

from infra.azure.validate import (
    REQUIRED_TAGS,
    validate_bootstrap_resource_group,
    validate_existing_resources,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AZURE_DIRECTORY = REPOSITORY_ROOT / "infra" / "azure"


def compact_bicep(filename: str) -> str:
    source = (AZURE_DIRECTORY / filename).read_text(encoding="utf-8")
    without_comments = re.sub(r"//.*$", "", source, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", without_comments)


def expected_manifest() -> dict[str, object]:
    return {
        "subscriptionId": "00000000-0000-0000-0000-000000000001",
        "resourceGroup": "rg-sort-tester-staging",
        "resources": [
            {
                "id": "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-sort-tester-staging/providers/Microsoft.Web/sites/st-sort-tester-demo",
                "name": "st-sort-tester-demo",
                "type": "Microsoft.Web/sites",
            }
        ],
    }


def observed_report() -> dict[str, object]:
    manifest = expected_manifest()
    return {
        "subscriptionId": manifest["subscriptionId"],
        "resourceGroup": manifest["resourceGroup"],
        "resources": [
            {
                **manifest["resources"][0],
                "tags": dict(REQUIRED_TAGS),
            }
        ],
    }


class BootstrapBoundaryTests(unittest.TestCase):
    def test_first_bootstrap_requires_absent_resource_group(self) -> None:
        absent = validate_bootstrap_resource_group(exists=False)
        existing = validate_bootstrap_resource_group(exists=True)

        self.assertTrue(absent.allowed)
        self.assertEqual(absent.blockers, ())
        self.assertFalse(existing.allowed)
        self.assertIn("RESOURCE_GROUP_ALREADY_EXISTS", existing.blockers)


class ExistingResourceValidationTests(unittest.TestCase):
    def test_accepts_only_the_exact_manifest_with_required_tags(self) -> None:
        decision = validate_existing_resources(
            observed_report(),
            expected_manifest(),
            REQUIRED_TAGS,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.blockers, ())

    def test_rejects_unexpected_resource_even_when_tags_match(self) -> None:
        report = observed_report()
        report["resources"].append(
            {
                "id": "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-sort-tester-staging/providers/Microsoft.Storage/storageAccounts/unexpected",
                "name": "unexpected",
                "type": "Microsoft.Storage/storageAccounts",
                "tags": dict(REQUIRED_TAGS),
            }
        )

        decision = validate_existing_resources(
            report,
            expected_manifest(),
            REQUIRED_TAGS,
        )

        self.assertFalse(decision.allowed)
        self.assertIn("UNEXPECTED_RESOURCE", decision.blockers)

    def test_rejects_missing_resource_or_identity_mismatch(self) -> None:
        cases = {
            "MISSING_RESOURCE": lambda report: report["resources"].clear(),
            "RESOURCE_IDENTITY_MISMATCH": lambda report: report["resources"][0].update(
                name="renamed"
            ),
            "RESOURCE_TAG_MISMATCH": lambda report: report["resources"][0]["tags"].update(
                environment="production"
            ),
        }

        for expected_blocker, mutate in cases.items():
            with self.subTest(expected_blocker=expected_blocker):
                report = observed_report()
                mutate(report)

                decision = validate_existing_resources(
                    report,
                    expected_manifest(),
                    REQUIRED_TAGS,
                )

                self.assertFalse(decision.allowed)
                self.assertIn(expected_blocker, decision.blockers)

    def test_rejects_wrong_boundary_and_duplicate_ids(self) -> None:
        cases = {
            "SUBSCRIPTION_MISMATCH": lambda report: report.update(
                subscriptionId="00000000-0000-0000-0000-000000000099"
            ),
            "RESOURCE_GROUP_MISMATCH": lambda report: report.update(
                resourceGroup="rg-unrelated"
            ),
            "DUPLICATE_RESOURCE_ID": lambda report: report["resources"].append(
                dict(report["resources"][0])
            ),
        }

        for expected_blocker, mutate in cases.items():
            with self.subTest(expected_blocker=expected_blocker):
                report = observed_report()
                mutate(report)

                decision = validate_existing_resources(
                    report,
                    expected_manifest(),
                    REQUIRED_TAGS,
                )

                self.assertFalse(decision.allowed)
                self.assertIn(expected_blocker, decision.blockers)


class BicepContractTests(unittest.TestCase):
    def test_bootstrap_creates_only_the_tagged_staging_group(self) -> None:
        source = compact_bicep("bootstrap-resource-group.bicep")

        self.assertIn("targetScope = 'subscription'", source)
        self.assertIn("'rg-sort-tester-staging'", source)
        self.assertEqual(source.count("resource "), 1)
        self.assertIn("Microsoft.Resources/resourceGroups@", source)
        for key, value in REQUIRED_TAGS.items():
            self.assertIn(f"'{key}': '{value}'", source)

    def test_main_enforces_identity_https_tls_and_entra_only_postgres(self) -> None:
        source = compact_bicep("main.bicep")

        for key, value in REQUIRED_TAGS.items():
            self.assertIn(f"'{key}': '{value}'", source)
        self.assertIn("httpsOnly: true", source)
        self.assertIn("minTlsVersion: '1.2'", source)
        self.assertIn("linuxFxVersion: 'PYTHON|3.14'", source)
        self.assertIn("type: 'SystemAssigned'", source)
        self.assertIn("version: '18'", source)
        self.assertIn("activeDirectoryAuth: 'Enabled'", source)
        self.assertIn("passwordAuth: 'Disabled'", source)
        self.assertRegex(source, r"backupRetentionDays:\s*(7|14|21|28|30|35)")
        self.assertIn("Microsoft.DBforPostgreSQL/flexibleServers/administrators@", source)
        self.assertIn("publicNetworkAccess: 'Enabled'", source)

    def test_main_caps_telemetry_and_defines_no_broad_firewall(self) -> None:
        source = compact_bicep("main.bicep")

        self.assertIn("retentionInDays: 30", source)
        self.assertRegex(source, r"dailyQuotaGb:\s*0\.\d+")
        self.assertNotIn("firewallRules@", source)
        self.assertNotIn("0.0.0.0", source)
        self.assertNotIn("255.255.255.255", source)
        self.assertNotIn("AllowAllAzure", source)

    def test_main_defines_the_approved_monthly_budget_alerts(self) -> None:
        source = compact_bicep("main.bicep")

        self.assertIn("Microsoft.Consumption/budgets@", source)
        self.assertIn("amount: 5", source)
        self.assertIn("timeGrain: 'Monthly'", source)
        for threshold in (50, 80, 100):
            self.assertIn(f"threshold: {threshold}", source)

    def test_runbook_requires_absence_check_and_what_if_before_deployment(self) -> None:
        readme = (AZURE_DIRECTORY / "README.md").read_text(encoding="utf-8")

        self.assertIn("az group exists", readme)
        self.assertIn("az deployment sub what-if", readme)
        self.assertIn("az deployment group what-if", readme)
        self.assertIn("must print `false`", readme)

    def test_templates_contain_no_literal_credential(self) -> None:
        sources = " ".join(
            compact_bicep(filename)
            for filename in (
                "bootstrap-resource-group.bicep",
                "main.bicep",
                "main.staging.bicepparam",
            )
        )

        forbidden = ("administratorLoginPassword", "connectionString", "clientSecret")
        for value in forbidden:
            self.assertNotIn(value, sources)


if __name__ == "__main__":
    unittest.main()
