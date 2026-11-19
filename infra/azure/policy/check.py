"""Offline infrastructure policy validation for the Azure Bicep templates.

This is the "additional validation" of issue #205. It is deliberately NOT a
live `az deployment group what-if`: it needs no Azure credential, no network
and no subscription, so a pull request from any branch can run it without
being granted any Azure access or deployment authority (issue #205 item 4).

What it reads
-------------
It evaluates the ARM JSON that `az bicep build` emits from the templates in
`infra/azure/*.bicep`. That compiled form is the same artefact a what-if would
send to Azure, so a rule written against it describes the real request, not the
Bicep sugar around it.

What it asserts
---------------
It does not diff two deployments and it does not try to decide whether a change
is a "platform default" or a "revision-scope" detail -- that reading is exactly
what the manual, owner-reviewed what-if exists to do, and what the recorded
evidence in `final-verification-2026-11-18.md` already does by hand. Instead it
asserts a fixed set of security *invariants* that the reviewed baseline holds
and that must keep holding: HTTPS-only ingress, images pinned by digest, no
plaintext database credential in a template, a registry with admin and
anonymous pull off, a Key Vault on RBAC with soft delete, the GitHub OIDC
issuer unchanged, and no broad Azure role (Owner / Contributor / User Access
Administrator) handed out by a role assignment.

Because it checks invariants rather than diffing, it never blanket-ignores a
Modify or a Delete (issue #205 item 2): flipping `allowInsecure` to true, or
widening a role assignment to Contributor, fails the job whether that arrived
as a Modify, a Delete-and-recreate or a brand new resource. It equally does not
flag the benign tag / location / scale / revision-suffix churn that the manual
what-if review already accounts for, because those are not invariants here.

Usage
-----
    python infra/azure/policy/check.py compiled/*.json

Each argument is a compiled ARM template (one JSON object). The process exits
non-zero if any template violates an invariant, printing every finding. With no
violations it prints a one-line pass per template and exits 0.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Iterable


# Built-in Azure role definition GUIDs that grant broad control-plane power.
# A pull request's infrastructure must never assign one of these: the running
# identities hold only AcrPull, AcrPush and Key Vault Secrets User (audit H-5).
# GUIDs are from Microsoft's published built-in role list.
BROAD_ROLE_GUIDS: dict[str, str] = {
    "8e3af657-a8ff-443c-a75c-2fe8c4bcb635": "Owner",
    "b24988ac-6180-42a0-ab88-20f7382dd24c": "Contributor",
    "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9": "User Access Administrator",
    # Role Based Access Control Administrator can itself grant the above.
    "f58310d9-a9f6-439a-9e8d-f62e7b41a168": "Role Based Access Control Administrator",
}

# The only issuer a federated credential in this repository should ever trust.
GITHUB_OIDC_ISSUER = "https://token.actions.githubusercontent.com"


@dataclass(frozen=True)
class Finding:
    rule: str
    resource: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.resource}: {self.detail}"


def _iter_resources(template: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield every resource in the template, including nested child resources.

    Compiled ARM usually lists child resources at the top level with their full
    type, but a hand-written or differently compiled template may nest them
    under a parent's ``resources`` array. Both are flattened so a rule never
    silently skips a resource because of where it sits.
    """

    def walk(resources: Any) -> Iterable[dict[str, Any]]:
        if not isinstance(resources, list):
            return
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            yield resource
            yield from walk(resource.get("resources"))

    yield from walk(template.get("resources"))


def _name(resource: dict[str, Any]) -> str:
    return f"{resource.get('type', '?')} {resource.get('name', '?')}"


def _as_text(value: Any) -> str:
    """Render a property value as text so a literal or an ARM expression (which
    compiles to a ``[...]`` string) can both be inspected for a substring."""

    if isinstance(value, str):
        return value
    return json.dumps(value)


def _is_false(value: Any) -> bool:
    return value is False


def _is_true(value: Any) -> bool:
    return value is True


def _check_container_app(resource: dict[str, Any], findings: list[Finding]) -> None:
    props = resource.get("properties") or {}
    ingress = (props.get("configuration") or {}).get("ingress") or {}
    # HTTPS only. allowInsecure must be explicitly false; a missing value would
    # let a template drift to the platform default without review, so absence
    # is treated as a finding too.
    if "allowInsecure" in ingress:
        if not _is_false(ingress.get("allowInsecure")):
            findings.append(Finding(
                "ingress-https-only", _name(resource),
                f"configuration.ingress.allowInsecure is {ingress.get('allowInsecure')!r}, must be false",
            ))
    else:
        findings.append(Finding(
            "ingress-https-only", _name(resource),
            "configuration.ingress has no allowInsecure; HTTPS-only must be stated, not defaulted",
        ))

    # Every container image must be pinned by digest, never a mutable tag.
    for container in (props.get("template") or {}).get("containers") or []:
        if not isinstance(container, dict):
            continue
        image = _as_text(container.get("image", ""))
        if "@sha256:" not in image:
            findings.append(Finding(
                "image-digest-pinned", _name(resource),
                f"container {container.get('name', '?')!r} image is not pinned by @sha256: digest ({image})",
            ))

    # No inline plaintext secret value. A Key Vault reference or a secretRef is
    # fine; a literal, non-empty, non-expression value is a credential in the
    # template. The reviewed app template fills this from a parameter or a vault
    # URI, so a literal here is always a regression.
    for secret in (props.get("configuration") or {}).get("secrets") or []:
        if not isinstance(secret, dict):
            continue
        value = secret.get("value")
        if isinstance(value, str) and value and not value.startswith("["):
            findings.append(Finding(
                "no-plaintext-secret", _name(resource),
                f"secret {secret.get('name', '?')!r} carries an inline literal value",
            ))


def _check_registry(resource: dict[str, Any], findings: list[Finding]) -> None:
    props = resource.get("properties") or {}
    if not _is_false(props.get("adminUserEnabled")):
        findings.append(Finding(
            "registry-admin-off", _name(resource),
            f"properties.adminUserEnabled is {props.get('adminUserEnabled')!r}, must be false",
        ))
    if not _is_false(props.get("anonymousPullEnabled")):
        findings.append(Finding(
            "registry-anon-pull-off", _name(resource),
            f"properties.anonymousPullEnabled is {props.get('anonymousPullEnabled')!r}, must be false",
        ))


def _check_key_vault(resource: dict[str, Any], findings: list[Finding]) -> None:
    props = resource.get("properties") or {}
    if not _is_true(props.get("enableRbacAuthorization")):
        findings.append(Finding(
            "keyvault-rbac", _name(resource),
            f"properties.enableRbacAuthorization is {props.get('enableRbacAuthorization')!r}, must be true",
        ))
    if not _is_true(props.get("enableSoftDelete")):
        findings.append(Finding(
            "keyvault-soft-delete", _name(resource),
            f"properties.enableSoftDelete is {props.get('enableSoftDelete')!r}, must be true",
        ))


def _check_role_assignment(resource: dict[str, Any], findings: list[Finding]) -> None:
    props = resource.get("properties") or {}
    role = _as_text(props.get("roleDefinitionId", "")).lower()
    for guid, label in BROAD_ROLE_GUIDS.items():
        if guid in role:
            findings.append(Finding(
                "no-broad-role", _name(resource),
                f"role assignment references the broad {label} role ({guid})",
            ))


def _check_federated_credential(resource: dict[str, Any], findings: list[Finding]) -> None:
    props = resource.get("properties") or {}
    issuer = _as_text(props.get("issuer", ""))
    # Only guard the issuer here: the subject is a reviewed parameter, not a
    # literal, so it cannot be judged statically (documented coverage limit).
    if issuer and issuer != GITHUB_OIDC_ISSUER:
        findings.append(Finding(
            "oidc-issuer", _name(resource),
            f"federated credential issuer is {issuer!r}, must be {GITHUB_OIDC_ISSUER!r}",
        ))


def evaluate(template: dict[str, Any]) -> list[Finding]:
    """Return every invariant violation in one compiled ARM template."""

    findings: list[Finding] = []
    for resource in _iter_resources(template):
        resource_type = str(resource.get("type", "")).lower()
        if resource_type == "microsoft.app/containerapps":
            _check_container_app(resource, findings)
        elif resource_type == "microsoft.containerregistry/registries":
            _check_registry(resource, findings)
        elif resource_type == "microsoft.keyvault/vaults":
            _check_key_vault(resource, findings)
        elif resource_type == "microsoft.authorization/roleassignments":
            _check_role_assignment(resource, findings)
        elif resource_type == "microsoft.managedidentity/userassignedidentities/federatedidentitycredentials":
            _check_federated_credential(resource, findings)
    return findings


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python infra/azure/policy/check.py <compiled-arm.json> ...", file=sys.stderr)
        return 2

    total = 0
    for path in argv:
        try:
            with open(path, encoding="utf-8") as handle:
                template = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            print(f"could not read {path}: {error}", file=sys.stderr)
            return 2
        if not isinstance(template, dict):
            print(f"{path}: not an ARM template object", file=sys.stderr)
            return 2

        findings = evaluate(template)
        if findings:
            total += len(findings)
            print(f"FAIL {path}")
            for finding in findings:
                print(f"  {finding}")
        else:
            print(f"ok   {path}")

    if total:
        print(f"\n{total} policy violation(s) found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
