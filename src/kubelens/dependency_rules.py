"""Evidence-linked missing configuration dependency rules."""

from kubelens.models import (
    Evidence,
    Finding,
    ResourceReference,
    serialize_model,
)


def enrich_dependencies(payload: dict, report) -> dict:
    """Attach dependency evidence and confirmed missing-resource findings."""

    for dependency in report.dependencies:
        resource = ResourceReference(
            kind="Pod",
            namespace=report.namespace,
            name=report.pod,
            container=dependency["container"],
        )

        evidence = Evidence(
            id=f"evidence-{len(payload['evidence']) + 1:03d}",
            source="kubernetes.resource_metadata",
            resource=resource,
            field=(
                f"dependency.{dependency['kind']}."
                f"{dependency['name']}.availability"
            ),
            value=dependency["availability"],
        )

        payload["evidence"].append(serialize_model(evidence))

        # A missing resource is linked to the current container error,
        # not to an unrelated container or an old Event.
        matching_container = next(
            (
                item
                for item in report.containers
                if item["name"] == dependency["container"]
            ),
            None,
        )

        if not matching_container:
            continue

        if matching_container.get("waiting_reason") != (
            "CreateContainerConfigError"
        ):
            continue

        if dependency["availability"] != "missing":
            continue

        waiting_evidence = next(
            (
                item["id"]
                for item in payload["evidence"]
                if item["source"] == "kubernetes.container_status"
                and item["resource"]["container"]
                == dependency["container"]
                and item["field"] == "waiting_reason"
                and item["value"] == "CreateContainerConfigError"
            ),
            None,
        )

        refs = [evidence.id]
        if waiting_evidence:
            refs.insert(0, waiting_evidence)

        kind = dependency["kind"]

        finding = Finding(
            id=f"finding-{len(payload['findings']) + 1:03d}",
            rule_id=(
                "dependency.missing_configmap"
                if kind == "ConfigMap"
                else "dependency.missing_secret"
            ),
            classification="confirmed_condition",
            severity="high",
            summary=(
                f"Required {kind} '{dependency['name']}' is missing"
            ),
            resource=resource,
            evidence_refs=refs,
            recommendations=[
                f"Verify the {kind} name and namespace, "
                "then create or restore the required resource."
            ],
        )

        payload["findings"].append(serialize_model(finding))

    payload["analysis_status"] = (
        "findings_detected"
        if payload["findings"]
        else "no_known_findings"
    )

    payload["limitations"].append(
        "Dependency checks currently cover required environment "
        "references; volume and key-level validation are not included."
    )

    return payload
