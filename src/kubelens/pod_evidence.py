"""Enrich structured reports with Pod conditions and Event evidence."""

from kubelens.event_records import normalize_events
from kubelens.dependency_rules import enrich_dependencies
from kubelens.models import (
    Evidence,
    Finding,
    ResourceReference,
    serialize_model,
)


def enrich_pod_evidence(payload: dict, report) -> dict:
    """Attach evidence and detect explicitly unschedulable Pods."""

    resource = ResourceReference(
        kind="Pod",
        namespace=report.namespace,
        name=report.pod,
    )

    def add_evidence(source: str, field: str, value) -> str:
        item = Evidence(
            id=f"evidence-{len(payload['evidence']) + 1:03d}",
            source=source,
            resource=resource,
            field=field,
            value=value,
        )
        payload["evidence"].append(serialize_model(item))
        return item.id

    unschedulable_refs = []

    for condition in report.conditions:
        condition_type = condition.get("type")
        status = condition.get("status")
        reason = condition.get("reason")

        if not condition_type:
            continue

        prefix = f"condition.{condition_type}"

        status_ref = add_evidence(
            "kubernetes.pod_condition",
            f"{prefix}.status",
            status,
        )

        reason_ref = None
        if reason:
            reason_ref = add_evidence(
                "kubernetes.pod_condition",
                f"{prefix}.reason",
                reason,
            )

        if (
            condition_type == "PodScheduled"
            and status == "False"
            and reason == "Unschedulable"
        ):
            unschedulable_refs.append(status_ref)
            if reason_ref:
                unschedulable_refs.append(reason_ref)

    # Preserve each Event as one coherent observation.
    payload["events"] = []

    for event in normalize_events(report.event_records):
        payload["events"].append({
            **event,
            "resource": serialize_model(resource),
        })

        # Keep evidence references compatible with existing rules.
        evidence_ref = add_evidence(
            "kubernetes.event",
            "event.reason",
            event["reason"],
        )

        # Connect the evidence to its complete Event record.
        payload["evidence"][-1]["event_ref"] = event["id"]

        # Historical Events support findings but do not independently
        # establish the current Pod scheduling condition.
        if (
            event["reason"] == "FailedScheduling"
            and unschedulable_refs
        ):
            unschedulable_refs.append(evidence_ref)

    if unschedulable_refs:
        finding = Finding(
            id=f"finding-{len(payload['findings']) + 1:03d}",
            rule_id="pod.unschedulable",
            classification="confirmed_condition",
            severity="high",
            summary="Kubernetes reports that the Pod is unschedulable",
            resource=resource,
            evidence_refs=list(dict.fromkeys(unschedulable_refs)),
            recommendations=[
                "Inspect FailedScheduling Events, node capacity, "
                "resource requests, taints, and scheduling constraints."
            ],
        )
        payload["findings"].append(serialize_model(finding))

    payload["analysis_status"] = (
        "findings_detected"
        if payload["findings"]
        else "no_known_findings"
    )

    payload["limitations"] = [
        "Only implemented container and Pod scheduling rules are evaluated.",
        "Event records do not establish application root cause.",
        "No historical metrics are available in this report.",
        "No known findings does not mean the Pod is healthy.",
    ]

    return enrich_dependencies(payload, report)
