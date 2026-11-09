"""Read-only Azure staging preflight.

This module deliberately separates Azure CLI collection from the pure decision
function so the safety policy can be tested without an Azure account.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Mapping, Protocol, Sequence


REQUIRED_REGIONS = ("eastus2", "eastus")
PLANNED_RESOURCE_PREFIXES = (
    "rg-sort-tester-staging",
    "sort-tester-staging",
    "stsorttester",
)
POSTGRES_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


@dataclass(frozen=True)
class PreflightDecision:
    allowed: bool
    blockers: tuple[str, ...]
    evidence: dict[str, object]


class AzureCli(Protocol):
    def json(self, *arguments: str) -> object:
        """Run one approved read-only Azure CLI command and parse its JSON."""


class SubprocessAzureCli:
    """Azure CLI adapter with an explicit read-only command allowlist."""

    _ALLOWED_PREFIXES = (
        ("account", "show"),
        ("account", "list-locations"),
        ("webapp", "list-runtimes"),
        ("appservice", "list-locations"),
        ("postgres", "flexible-server", "list-skus"),
        ("resource", "list"),
    )

    def json(self, *arguments: str) -> object:
        command = tuple(arguments)
        if not any(command[: len(prefix)] == prefix for prefix in self._ALLOWED_PREFIXES):
            raise ValueError("Azure preflight attempted a command outside its read-only allowlist")
        try:
            completed = subprocess.run(
                ["az", *arguments, "--output", "json", "--only-show-errors"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return json.loads(completed.stdout)
        except FileNotFoundError as error:
            raise RuntimeError("Azure CLI is not installed or is unavailable") from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("Azure read command exceeded 30 seconds") from error
        except subprocess.CalledProcessError as error:
            safe_command = "az " + " ".join(arguments[:3])
            raise RuntimeError(f"Azure read command failed: {safe_command}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError("Azure read command returned invalid JSON") from error


def _contains_text(value: object, expected: str) -> bool:
    if isinstance(value, str):
        return expected.casefold() in value.casefold()
    if isinstance(value, Mapping):
        return any(_contains_text(item, expected) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_text(item, expected) for item in value)
    return False


def _location_names(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    names: set[str] = set()
    for item in value:
        if isinstance(item, str):
            names.add("".join(character for character in item.casefold() if character.isalnum()))
        elif isinstance(item, Mapping) and isinstance(item.get("name"), str):
            names.add(
                "".join(
                    character
                    for character in item["name"].casefold()
                    if character.isalnum()
                )
            )
    return names


def _named_capabilities(value: object, capability_name: str) -> set[str]:
    names: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() == capability_name.casefold() and isinstance(item, list):
                for capability in item:
                    if isinstance(capability, str):
                        names.add(capability.casefold())
                    elif isinstance(capability, Mapping) and isinstance(capability.get("name"), str):
                        names.add(capability["name"].casefold())
            else:
                names.update(_named_capabilities(item, capability_name))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            names.update(_named_capabilities(item, capability_name))
    return names


def _planned_collisions(resources: object) -> list[dict[str, object]]:
    if not isinstance(resources, list):
        return [{"name": "INVALID_RESOURCE_LIST", "type": "unknown"}]
    collisions: list[dict[str, object]] = []
    for resource in resources:
        if not isinstance(resource, Mapping):
            collisions.append({"name": "INVALID_RESOURCE_RECORD", "type": "unknown"})
            continue
        name = str(resource.get("name", ""))
        group = str(resource.get("resourceGroup", ""))
        if any(
            candidate.casefold().startswith(prefix.casefold())
            for candidate in (name, group)
            for prefix in PLANNED_RESOURCE_PREFIXES
        ):
            collisions.append(
                {
                    "name": name,
                    "resourceGroup": group,
                    "type": str(resource.get("type", "unknown")),
                    "tags": dict(resource.get("tags") or {}),
                }
            )
    return collisions


def collect_preflight(
    cli: AzureCli,
    *,
    expected_subscription_name: str,
    expected_subscription_id: str,
    manual_review: Mapping[str, object],
) -> dict[str, object]:
    """Collect only the evidence needed by :func:`evaluate_preflight`.

    Tenant ID, user identity, raw subscription ID, and unrelated resources are
    deliberately omitted from the returned report.
    """

    account = cli.json("account", "show")
    if not isinstance(account, Mapping):
        raise RuntimeError("Azure account response has an unexpected shape")
    locations = _location_names(cli.json("account", "list-locations"))
    runtimes = cli.json("webapp", "list-runtimes", "--os-type", "linux")
    app_service_locations = _location_names(
        cli.json("appservice", "list-locations", "--sku", "F1", "--linux-workers-enabled")
    )
    resources = cli.json("resource", "list")

    regions: dict[str, dict[str, bool]] = {}
    python_314_available = _contains_text(runtimes, "PYTHON|3.14")
    for region in REQUIRED_REGIONS:
        postgres_skus = cli.json(
            "postgres",
            "flexible-server",
            "list-skus",
            "--location",
            region,
        )
        postgres_versions = _named_capabilities(postgres_skus, "supportedServerVersions")
        postgres_sku_names = _named_capabilities(postgres_skus, "supportedServerSkus")
        regions[region] = {
            "linuxPython314": python_314_available and region in locations,
            "appServiceF1": region in app_service_locations,
            "postgres18": "18" in postgres_versions
            and "standard_b1ms" in postgres_sku_names,
        }

    subscription_id = str(account.get("id", ""))
    subscription_name = str(account.get("name", ""))
    subscription_fingerprint = (
        hashlib.sha256(subscription_id.encode("utf-8")).hexdigest()[:12]
        if subscription_id
        else "missing"
    )
    return {
        "schemaVersion": 2,
        "collectedAtUtc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "subscription": {
            "name": subscription_name,
            "fingerprint": subscription_fingerprint,
            "expected": subscription_name == expected_subscription_name
            and subscription_id == expected_subscription_id,
            "enabled": str(account.get("state", "")).casefold() == "enabled",
        },
        "spendingLimit": {
            "confirmedEnabled": bool(manual_review.get("spendingLimitConfirmed")),
        },
        "manualReview": {
            "studentTermsReviewed": bool(manual_review.get("studentTermsReviewed")),
            "appServiceFreeConfirmed": bool(manual_review.get("appServiceFreeConfirmed")),
            "postgresFreeConfirmed": bool(manual_review.get("postgresFreeConfirmed")),
            "grossMonthlyRetailEstimateUsd": manual_review.get(
                "grossMonthlyRetailEstimateUsd"
            ),
            "expectedMonthlyChargeUsd": manual_review.get(
                "expectedMonthlyChargeUsd"
            ),
            "paidUsageApproved": bool(manual_review.get("paidUsageApproved")),
        },
        "regions": regions,
        "plannedResourceCollisions": _planned_collisions(resources),
        "authenticationPlan": {
            "postgres": "Microsoft Entra only",
            "runtime": "App Service system-assigned managed identity",
            "tokenScope": POSTGRES_TOKEN_SCOPE,
        },
    }


def evaluate_preflight(evidence: Mapping[str, object]) -> PreflightDecision:
    """Apply the owner-approved no-create Azure staging gates."""

    blockers: list[str] = []
    subscription = evidence.get("subscription")
    spending_limit = evidence.get("spendingLimit")
    manual = evidence.get("manualReview")
    regions = evidence.get("regions")
    collisions = evidence.get("plannedResourceCollisions")

    if not isinstance(subscription, Mapping) or not subscription.get("expected"):
        blockers.append("SUBSCRIPTION_UNEXPECTED")
    if not isinstance(subscription, Mapping) or not subscription.get("enabled"):
        blockers.append("SUBSCRIPTION_DISABLED")
    if not isinstance(spending_limit, Mapping) or not spending_limit.get("confirmedEnabled"):
        blockers.append("SPENDING_LIMIT_UNCONFIRMED")

    paid_approved = isinstance(manual, Mapping) and bool(manual.get("paidUsageApproved"))
    if not isinstance(manual, Mapping) or not manual.get("studentTermsReviewed"):
        blockers.append("STUDENT_TERMS_UNREVIEWED")
    if (not isinstance(manual, Mapping) or not manual.get("appServiceFreeConfirmed")) and not paid_approved:
        blockers.append("APP_SERVICE_FREE_UNCONFIRMED")
    if (not isinstance(manual, Mapping) or not manual.get("postgresFreeConfirmed")) and not paid_approved:
        blockers.append("POSTGRES_FREE_UNCONFIRMED")

    estimate_fields = (
        (
            "grossMonthlyRetailEstimateUsd",
            "RETAIL_ESTIMATE_MISSING",
            "RETAIL_ESTIMATE_INVALID",
        ),
        (
            "expectedMonthlyChargeUsd",
            "EXPECTED_CHARGE_MISSING",
            "EXPECTED_CHARGE_INVALID",
        ),
    )
    estimates: dict[str, Decimal] = {}
    for field, missing_blocker, invalid_blocker in estimate_fields:
        estimate_value = manual.get(field) if isinstance(manual, Mapping) else None
        if estimate_value is None:
            blockers.append(missing_blocker)
            continue
        try:
            estimate = Decimal(str(estimate_value))
            if not estimate.is_finite() or estimate < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            blockers.append(invalid_blocker)
            continue
        estimates[field] = estimate

    expected_charge = estimates.get("expectedMonthlyChargeUsd")
    if expected_charge is not None and expected_charge > 0 and not paid_approved:
        blockers.append("PAID_USAGE_NOT_APPROVED")

    if not isinstance(collisions, list) or collisions:
        blockers.append("RESOURCE_NAME_COLLISION")

    selected_region: str | None = None
    if isinstance(regions, Mapping):
        for region in REQUIRED_REGIONS:
            capabilities = regions.get(region)
            if isinstance(capabilities, Mapping) and all(
                capabilities.get(requirement)
                for requirement in ("linuxPython314", "appServiceF1", "postgres18")
            ):
                selected_region = region
                break
    if selected_region is None:
        blockers.append("NO_COMPLETE_REGION")

    report_evidence = dict(evidence)
    report_evidence["selectedRegion"] = selected_region
    return PreflightDecision(
        allowed=not blockers,
        blockers=tuple(blockers),
        evidence=report_evidence,
    )


def _private_state_directory() -> Path:
    home_value = os.environ.get("HOME")
    if not home_value:
        raise ValueError("HOME must be set")
    home = Path(home_value).absolute()
    base = home / ".local" / "state" / "sort-tester-live"
    for component in (home / ".local", home / ".local" / "state", base):
        if component.is_symlink():
            raise ValueError("Private state path must not contain symlinks")
        component.mkdir(mode=0o700, exist_ok=True)
    os.chmod(base, 0o700)
    return base


def write_private_report(output: Path, report: Mapping[str, object]) -> None:
    """Create one private report without following links or overwriting data."""

    base = _private_state_directory()
    candidate = output.expanduser().absolute()
    if candidate.parent != base or candidate.name in {"", ".", ".."}:
        raise ValueError(f"Report must be a direct child of {base}")
    if candidate.is_symlink():
        raise ValueError("Report path must not be a symlink")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(candidate, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except BaseException:
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect read-only Azure staging evidence")
    parser.add_argument("--expected-subscription-name", required=True)
    parser.add_argument("--expected-subscription-id", required=True)
    parser.add_argument("--confirm-spending-limit-enabled", action="store_true")
    parser.add_argument("--confirm-student-terms-reviewed", action="store_true")
    parser.add_argument("--confirm-app-service-free", action="store_true")
    parser.add_argument("--confirm-postgres-free", action="store_true")
    parser.add_argument("--gross-monthly-retail-usd", required=True)
    parser.add_argument("--expected-monthly-charge-usd", required=True)
    parser.add_argument("--approve-paid-usage", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    options = _parser().parse_args(arguments)
    evidence = collect_preflight(
        SubprocessAzureCli(),
        expected_subscription_name=options.expected_subscription_name,
        expected_subscription_id=options.expected_subscription_id,
        manual_review={
            "spendingLimitConfirmed": options.confirm_spending_limit_enabled,
            "studentTermsReviewed": options.confirm_student_terms_reviewed,
            "appServiceFreeConfirmed": options.confirm_app_service_free,
            "postgresFreeConfirmed": options.confirm_postgres_free,
            "grossMonthlyRetailEstimateUsd": options.gross_monthly_retail_usd,
            "expectedMonthlyChargeUsd": options.expected_monthly_charge_usd,
            "paidUsageApproved": options.approve_paid_usage,
        },
    )
    decision = evaluate_preflight(evidence)
    output = options.output
    if output is None:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output = _private_state_directory() / f"azure-preflight-{timestamp}.json"
    write_private_report(
        output,
        {
            "decision": {
                "allowed": decision.allowed,
                "blockers": list(decision.blockers),
            },
            "evidence": decision.evidence,
        },
    )
    print(f"Private report written to: {output.expanduser().absolute()}")
    print("Decision: " + ("READY FOR OWNER REVIEW" if decision.allowed else "BLOCKED"))
    if decision.blockers:
        print("Blockers: " + ", ".join(decision.blockers))
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
