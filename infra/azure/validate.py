"""Pure ownership checks for the Azure staging boundary.

The functions in this module never call Azure.  They validate already-collected
JSON so a deployment or cleanup caller can stop before mutating the wrong
subscription, resource group, or resource.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


REQUIRED_TAGS: dict[str, str] = {
    "project": "sort-tester-live",
    "environment": "staging",
    "data-classification": "fictional-only",
    "expires-on": "2027-10-09",
}


@dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    blockers: tuple[str, ...]


def validate_bootstrap_resource_group(*, exists: bool) -> ValidationResult:
    """Allow the one-time bootstrap only when the group is absent."""

    blockers = ("RESOURCE_GROUP_ALREADY_EXISTS",) if exists else ()
    return ValidationResult(allowed=not blockers, blockers=blockers)


def _records(value: object) -> list[Mapping[str, object]] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    if not all(isinstance(item, Mapping) for item in value):
        return None
    return list(value)


def _identity(record: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(record.get("id", "")).casefold(),
        str(record.get("name", "")).casefold(),
        str(record.get("type", "")).casefold(),
    )


def validate_existing_resources(
    report: Mapping[str, object],
    manifest: Mapping[str, object],
    expected_tags: Mapping[str, str],
) -> ValidationResult:
    """Require an exact manifest match before later mutation or cleanup.

    Tags are necessary but never sufficient.  The subscription, resource group,
    resource IDs, names, types, and required tag values must all match.
    """

    blockers: list[str] = []
    if str(report.get("subscriptionId", "")) != str(manifest.get("subscriptionId", "")):
        blockers.append("SUBSCRIPTION_MISMATCH")
    if str(report.get("resourceGroup", "")).casefold() != str(
        manifest.get("resourceGroup", "")
    ).casefold():
        blockers.append("RESOURCE_GROUP_MISMATCH")

    observed = _records(report.get("resources"))
    expected = _records(manifest.get("resources"))
    if observed is None or expected is None:
        blockers.append("INVALID_RESOURCE_RECORDS")
        return ValidationResult(False, tuple(dict.fromkeys(blockers)))

    observed_ids = [str(item.get("id", "")).casefold() for item in observed]
    expected_ids = [str(item.get("id", "")).casefold() for item in expected]
    if len(observed_ids) != len(set(observed_ids)) or len(expected_ids) != len(
        set(expected_ids)
    ):
        blockers.append("DUPLICATE_RESOURCE_ID")

    observed_by_id = {str(item.get("id", "")).casefold(): item for item in observed}
    expected_by_id = {str(item.get("id", "")).casefold(): item for item in expected}

    if expected_by_id.keys() - observed_by_id.keys():
        blockers.append("MISSING_RESOURCE")
    if observed_by_id.keys() - expected_by_id.keys():
        blockers.append("UNEXPECTED_RESOURCE")

    for resource_id in observed_by_id.keys() & expected_by_id.keys():
        observed_record = observed_by_id[resource_id]
        expected_record = expected_by_id[resource_id]
        if _identity(observed_record) != _identity(expected_record):
            blockers.append("RESOURCE_IDENTITY_MISMATCH")
        tags = observed_record.get("tags")
        if not isinstance(tags, Mapping) or any(
            str(tags.get(key, "")) != value for key, value in expected_tags.items()
        ):
            blockers.append("RESOURCE_TAG_MISMATCH")

    unique_blockers = tuple(dict.fromkeys(blockers))
    return ValidationResult(allowed=not unique_blockers, blockers=unique_blockers)

