import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from infra.azure.preflight import (
    AzureCli,
    collect_preflight,
    evaluate_preflight,
    write_private_report,
)


def valid_evidence() -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "regionPolicy": {"verified": True, "allowedLocations": ["eastus2", "eastus"]},
        "subscription": {
            "expected": True,
            "enabled": True,
            "name": "Azure for Students",
        },
        "spendingLimit": {"confirmedEnabled": True},
        "manualReview": {
            "studentTermsReviewed": True,
            "appServiceFreeConfirmed": True,
            "postgresFreeConfirmed": True,
            "grossMonthlyRetailEstimateUsd": "16.49",
            "expectedMonthlyChargeUsd": "0.00",
            "paidUsageApproved": False,
        },
        "regions": {
            "eastus2": {
                "linuxPython314": True,
                "appServiceF1": True,
                "postgres18": True,
            },
            "eastus": {
                "linuxPython314": True,
                "appServiceF1": True,
                "postgres18": True,
            },
        },
        "plannedResourceCollisions": [],
    }


class EvaluatePreflightTests(unittest.TestCase):
    def test_global_capabilities_cannot_override_subscription_region_policy(self) -> None:
        evidence = valid_evidence()
        evidence["regionPolicy"]["allowedLocations"] = ["northcentralus"]
        evidence["regions"]["northcentralus"] = {"linuxPython314": True, "appServiceF1": True, "postgres18": True}
        decision = evaluate_preflight(evidence)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.evidence["selectedRegion"], "northcentralus")

    def test_missing_or_unverified_policy_fails_closed(self) -> None:
        for policy in (None, {}, {"verified": False, "allowedLocations": ["eastus2"]}, {"verified": True, "allowedLocations": []}):
            evidence = valid_evidence()
            evidence["regionPolicy"] = policy
            decision = evaluate_preflight(evidence)
            self.assertFalse(decision.allowed)
            self.assertIsNone(decision.evidence["selectedRegion"])

    def test_accepts_free_complete_eastus2_evidence_with_retail_exposure(self) -> None:
        decision = evaluate_preflight(valid_evidence())

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.blockers, ())
        self.assertEqual(decision.evidence["selectedRegion"], "eastus2")
        self.assertEqual(
            decision.evidence["manualReview"]["grossMonthlyRetailEstimateUsd"],
            "16.49",
        )
        self.assertEqual(
            decision.evidence["manualReview"]["expectedMonthlyChargeUsd"],
            "0.00",
        )

    def test_falls_back_to_eastus_only_when_eastus2_is_incomplete(self) -> None:
        evidence = valid_evidence()
        evidence["regions"]["eastus2"]["postgres18"] = False

        decision = evaluate_preflight(evidence)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.evidence["selectedRegion"], "eastus")

    def test_rejects_each_owner_gate_independently(self) -> None:
        mutations = {
            "SUBSCRIPTION_UNEXPECTED": lambda value: value["subscription"].update(expected=False),
            "SUBSCRIPTION_DISABLED": lambda value: value["subscription"].update(enabled=False),
            "SPENDING_LIMIT_UNCONFIRMED": lambda value: value["spendingLimit"].update(confirmedEnabled=False),
            "STUDENT_TERMS_UNREVIEWED": lambda value: value["manualReview"].update(studentTermsReviewed=False),
            "APP_SERVICE_FREE_UNCONFIRMED": lambda value: value["manualReview"].update(appServiceFreeConfirmed=False),
            "POSTGRES_FREE_UNCONFIRMED": lambda value: value["manualReview"].update(postgresFreeConfirmed=False),
            "RETAIL_ESTIMATE_MISSING": lambda value: value["manualReview"].update(
                grossMonthlyRetailEstimateUsd=None
            ),
            "EXPECTED_CHARGE_MISSING": lambda value: value["manualReview"].update(
                expectedMonthlyChargeUsd=None
            ),
            "RESOURCE_NAME_COLLISION": lambda value: value["plannedResourceCollisions"].append(
                {"name": "rg-sort-tester-staging", "type": "Microsoft.Resources/resourceGroups"}
            ),
        }

        for expected_blocker, mutate in mutations.items():
            with self.subTest(expected_blocker=expected_blocker):
                evidence = valid_evidence()
                mutate(evidence)
                decision = evaluate_preflight(evidence)
                self.assertFalse(decision.allowed)
                self.assertIn(expected_blocker, decision.blockers)

    def test_rejects_expected_charge_without_specific_approval(self) -> None:
        evidence = valid_evidence()
        evidence["manualReview"]["expectedMonthlyChargeUsd"] = "0.01"

        decision = evaluate_preflight(evidence)

        self.assertFalse(decision.allowed)
        self.assertIn("PAID_USAGE_NOT_APPROVED", decision.blockers)

    def test_accepts_expected_charge_only_after_specific_approval(self) -> None:
        evidence = valid_evidence()
        evidence["manualReview"].update(
            expectedMonthlyChargeUsd="4.25",
            paidUsageApproved=True,
        )

        decision = evaluate_preflight(evidence)

        self.assertTrue(decision.allowed)

    def test_rejects_invalid_retail_and_expected_amounts_independently(self) -> None:
        cases = {
            "RETAIL_ESTIMATE_INVALID": ("grossMonthlyRetailEstimateUsd", "not-money"),
            "EXPECTED_CHARGE_INVALID": ("expectedMonthlyChargeUsd", "-0.01"),
        }

        for expected_blocker, (field, invalid_value) in cases.items():
            with self.subTest(expected_blocker=expected_blocker):
                evidence = valid_evidence()
                evidence["manualReview"][field] = invalid_value

                decision = evaluate_preflight(evidence)

                self.assertFalse(decision.allowed)
                self.assertIn(expected_blocker, decision.blockers)

    def test_rejects_when_neither_region_has_every_required_capability(self) -> None:
        evidence = valid_evidence()
        evidence["regions"]["eastus2"]["postgres18"] = False
        evidence["regions"]["eastus"]["linuxPython314"] = False

        decision = evaluate_preflight(evidence)

        self.assertFalse(decision.allowed)
        self.assertIn("NO_COMPLETE_REGION", decision.blockers)
        self.assertIsNone(decision.evidence["selectedRegion"])


class RecordingAzureCli(AzureCli):
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def json(self, *arguments: str) -> object:
        self.commands.append(arguments)
        responses: dict[tuple[str, ...], object] = {
            ("policy", "assignment", "list"): [{"displayName": "Allowed locations", "parameters": {"listOfAllowedLocations": {"value": ["eastus2", "eastus", "northcentralus"]}}}],
            ("postgres", "flexible-server", "list-skus", "--location", "northcentralus"): [{"supportedServerVersions": [{"name": "18"}], "supportedServerSkus": [{"name": "Standard_B1ms"}]}],
            ("account", "show"): {
                "id": "11111111-1111-1111-1111-111111111111",
                "tenantId": "22222222-2222-2222-2222-222222222222",
                "name": "Azure for Students",
                "state": "Enabled",
                "user": {"name": "student@example.test", "type": "user"},
            },
            ("account", "list-locations"): [
                {"name": "eastus2"},
                {"name": "eastus"},
            ],
            ("webapp", "list-runtimes", "--os-type", "linux"): [
                {
                    "os": "Linux",
                    "runtime": "Python",
                    "version": "3.14",
                    "config": "PYTHON|3.14",
                    "support": "Active",
                }
            ],
            ("appservice", "list-locations", "--sku", "F1", "--linux-workers-enabled"): [
                {"name": "East US 2"},
                {"name": "East US"},
            ],
            ("postgres", "flexible-server", "list-skus", "--location", "eastus2"): [
                {
                    "name": "FlexibleServerCapabilities",
                    "supportedServerEditions": [
                        {
                            "name": "Burstable",
                            "supportedServerSkus": [{"name": "Standard_B1ms"}],
                        }
                    ],
                    "supportedServerVersions": [{"name": "18"}],
                }
            ],
            ("postgres", "flexible-server", "list-skus", "--location", "eastus"): [
                {
                    "name": "FlexibleServerCapabilities",
                    "supportedServerEditions": [
                        {
                            "name": "Burstable",
                            "supportedServerSkus": [{"name": "Standard_B1ms"}],
                        }
                    ],
                    "supportedServerVersions": [{"name": "18"}],
                }
            ],
            ("resource", "list"): [
                {
                    "id": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/unrelated/providers/Microsoft.Storage/storageAccounts/keepme",
                    "name": "keepme",
                    "resourceGroup": "unrelated",
                    "type": "Microsoft.Storage/storageAccounts",
                    "tags": {},
                }
            ],
        }
        return responses[arguments]


class CollectPreflightTests(unittest.TestCase):
    def test_collector_records_policy_and_intersects_multiple_constraints(self) -> None:
        class RestrictedCli(RecordingAzureCli):
            def json(self, *arguments: str) -> object:
                if arguments == ("policy", "assignment", "list"):
                    return [
                        {"parameters": {"listOfAllowedLocations": {"value": ["eastus2", "northcentralus"]}}},
                        {"parameters": {"listOfAllowedLocations": {"value": ["northcentralus"]}}},
                    ]
                return super().json(*arguments)
        evidence = collect_preflight(RestrictedCli(), expected_subscription_name="Azure for Students", expected_subscription_id="11111111-1111-1111-1111-111111111111", manual_review={})
        self.assertEqual(evidence["regionPolicy"]["allowedLocations"], ["northcentralus"])
        self.assertTrue(evidence["regionPolicy"]["verified"])

    def test_unreadable_or_missing_policy_does_not_become_unrestricted(self) -> None:
        class NoPolicyCli(RecordingAzureCli):
            def json(self, *arguments: str) -> object:
                if arguments == ("policy", "assignment", "list"):
                    raise RuntimeError("not readable")
                return super().json(*arguments)
        evidence = collect_preflight(NoPolicyCli(), expected_subscription_name="Azure for Students", expected_subscription_id="11111111-1111-1111-1111-111111111111", manual_review={})
        self.assertFalse(evidence["regionPolicy"]["verified"])

    def test_collector_uses_only_fixed_read_commands_and_redacts_identifiers(self) -> None:
        cli = RecordingAzureCli()

        evidence = collect_preflight(
            cli,
            expected_subscription_name="Azure for Students",
            expected_subscription_id="11111111-1111-1111-1111-111111111111",
            manual_review={
                "studentTermsReviewed": True,
                "appServiceFreeConfirmed": True,
                "postgresFreeConfirmed": True,
                "grossMonthlyRetailEstimateUsd": "16.49",
                "expectedMonthlyChargeUsd": "0.00",
                "paidUsageApproved": False,
                "spendingLimitConfirmed": True,
            },
        )

        allowed_prefixes = {
            ("policy", "assignment", "list"),
            ("account", "show"),
            ("account", "list-locations"),
            ("webapp", "list-runtimes"),
            ("appservice", "list-locations"),
            ("postgres", "flexible-server", "list-skus"),
            ("resource", "list"),
        }
        self.assertTrue(cli.commands)
        self.assertTrue(all(any(command[: len(prefix)] == prefix for prefix in allowed_prefixes) for command in cli.commands))
        rendered = json.dumps(evidence, sort_keys=True)
        self.assertNotIn("11111111-1111-1111-1111-111111111111", rendered)
        self.assertNotIn("22222222-2222-2222-2222-222222222222", rendered)
        self.assertNotIn("student@example.test", rendered)
        self.assertEqual(evidence["subscription"]["name"], "Azure for Students")
        self.assertEqual(evidence["plannedResourceCollisions"], [])
        self.assertEqual(
            evidence["regions"]["eastus2"],
            {
                "linuxPython314": True,
                "appServiceF1": True,
                "postgres18": True,
            },
        )
        self.assertEqual(
            evidence["manualReview"]["grossMonthlyRetailEstimateUsd"],
            "16.49",
        )
        self.assertEqual(
            evidence["manualReview"]["expectedMonthlyChargeUsd"],
            "0.00",
        )

    def test_collector_does_not_mistake_unrelated_numbers_for_postgres_18(self) -> None:
        class MissingPostgres18Cli(RecordingAzureCli):
            def json(self, *arguments: str) -> object:
                if arguments == (
                    "postgres",
                    "flexible-server",
                    "list-skus",
                    "--location",
                    "eastus2",
                ):
                    self.commands.append(arguments)
                    return [
                        {
                            "name": "FlexibleServerCapabilities",
                            "supportedServerEditions": [
                                {
                                    "name": "Burstable",
                                    "supportedServerSkus": [{"name": "Standard_B1ms"}],
                                }
                            ],
                            "supportedServerVersions": [{"name": "17"}],
                            "supportedStorageGb": ["18", "32"],
                        }
                    ]
                return super().json(*arguments)

        evidence = collect_preflight(
            MissingPostgres18Cli(),
            expected_subscription_name="Azure for Students",
            expected_subscription_id="11111111-1111-1111-1111-111111111111",
            manual_review={
                "studentTermsReviewed": True,
                "appServiceFreeConfirmed": True,
                "postgresFreeConfirmed": True,
                "grossMonthlyRetailEstimateUsd": "16.49",
                "expectedMonthlyChargeUsd": "0.00",
                "paidUsageApproved": False,
                "spendingLimitConfirmed": True,
            },
        )

        self.assertFalse(evidence["regions"]["eastus2"]["postgres18"])


class PrivateReportTests(unittest.TestCase):
    def test_report_writer_creates_private_state_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_home:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = temporary_home
            self.addCleanup(self._restore_home, old_home)
            output = Path(temporary_home) / ".local/state/sort-tester-live/report.json"

            write_private_report(output, {"allowed": False})

            directory_mode = stat.S_IMODE(output.parent.stat().st_mode)
            file_mode = stat.S_IMODE(output.stat().st_mode)
            self.assertEqual(directory_mode, 0o700)
            self.assertEqual(file_mode, 0o600)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"allowed": False})
            with self.assertRaises(FileExistsError):
                write_private_report(output, {"allowed": True})

    def test_report_writer_rejects_paths_outside_private_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_home:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = temporary_home
            self.addCleanup(self._restore_home, old_home)
            outside = Path(temporary_home) / "report.json"

            with self.assertRaises(ValueError):
                write_private_report(outside, {"allowed": False})

    def test_report_writer_refuses_symlink_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_home:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = temporary_home
            self.addCleanup(self._restore_home, old_home)
            real_directory = Path(temporary_home) / "real"
            real_directory.mkdir()
            state_parent = Path(temporary_home) / ".local/state"
            state_parent.mkdir(parents=True)
            (state_parent / "sort-tester-live").symlink_to(real_directory, target_is_directory=True)

            with self.assertRaises(ValueError):
                write_private_report(state_parent / "sort-tester-live/report.json", {"allowed": False})

    @staticmethod
    def _restore_home(old_home: str | None) -> None:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home


if __name__ == "__main__":
    unittest.main()
