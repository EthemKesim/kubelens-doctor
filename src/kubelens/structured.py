"""Build traceable reports from existing Kubernetes diagnostics."""

from kubelens.pod_evidence import enrich_pod_evidence

from kubelens.models import (
    Evidence,
    Finding,
    ResourceReference,
    serialize_model,
)


RULES = {
    "CrashLoopBackOff": (
        "container.crash_loop",
        "observed_symptom",
        "high",
        "Container is backing off after repeated failures",
        "Inspect previous container logs and exit codes.",
    ),
    "ImagePullBackOff": (
        "container.image_pull_backoff",
        "observed_symptom",
        "high",
        "Kubernetes is backing off container image pulls",
        "Verify the image reference and registry access.",
    ),
    "ErrImagePull": (
        "container.image_pull_error",
        "observed_symptom",
        "high",
        "Kubernetes could not pull the container image",
        "Inspect image pull Events and registry configuration.",
    ),
    "OOMKilled": (
        "container.oom_killed",
        "confirmed_condition",
        "high",
        "Container was terminated with OOMKilled",
        "Inspect memory limits and historical memory usage.",
    ),
}


def build_structured_report(report) -> dict:
    """Create a report with evidence-backed findings."""

    evidence = []
    findings = []

    pod_resource = ResourceReference(
        kind="Pod",
        namespace=report.namespace,
        name=report.pod,
    )

    for container in report.containers:
        resource = ResourceReference(
            kind="Pod",
            namespace=report.namespace,
            name=report.pod,
            container=container["name"],
        )

        # Record observations even when no rule matches.
        field_refs = {}

        fields = (
            "restart_count",
            "waiting_reason",
            "termination_reason",
            "exit_code",
            "previous_termination_reason",
            "previous_exit_code",
        )

        for field in fields:
            value = container.get(field)

            if value is None:
                continue

            item = Evidence(
                id=f"evidence-{len(evidence) + 1:03d}",
                source="kubernetes.container_status",
                resource=resource,
                field=field,
                value=value,
            )

            evidence.append(item)
            field_refs[field] = item.id

        reason_fields = (
            "waiting_reason",
            "termination_reason",
            "previous_termination_reason",
        )

        for field in reason_fields:
            reason = container.get(field)

            if reason in RULES:
                rule = RULES[reason]

            elif (
                field == "previous_termination_reason"
                and reason == "Error"
                and (container.get("restart_count") or 0) > 0
            ):
                rule = (
                    "container.previous_failure",
                    "observed_symptom",
                    "medium",
                    "Container previously exited with an error",
                    "Inspect previous logs and determine why it exited.",
                )

            else:
                continue

            rule_id, classification, severity, summary, action = rule

            refs = [field_refs[field]]

            if field == "termination_reason":
                code_field = "exit_code"
            elif field == "previous_termination_reason":
                code_field = "previous_exit_code"
            else:
                code_field = None

            if code_field and code_field in field_refs:
                refs.append(field_refs[code_field])

            if "restart_count" in field_refs:
                refs.append(field_refs["restart_count"])

            findings.append(
                Finding(
                    id=f"finding-{len(findings) + 1:03d}",
                    rule_id=rule_id,
                    classification=classification,
                    severity=severity,
                    summary=summary,
                    resource=resource,
                    evidence_refs=list(dict.fromkeys(refs)),
                    recommendations=[action],
                )
            )

    payload = {
        "schema_version": "2.0",
        "context": report.context,
        "namespace": report.namespace,
        "pod": report.pod,
        "resource": serialize_model(pod_resource),
        "findings": [serialize_model(item) for item in findings],
        "evidence": [serialize_model(item) for item in evidence],
        "analysis_status": (
            "findings_detected"
            if findings else "no_known_findings"
        ),
        "limitations": [
            "Only supported container-state rules are evaluated.",
            "No historical metrics or application-level root causes verified.",
            "No known findings does not mean the Pod is healthy.",
        ],
    }

    return enrich_pod_evidence(payload, report)
