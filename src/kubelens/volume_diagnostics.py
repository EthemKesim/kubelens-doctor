"""Read-only Kubernetes volume dependency diagnostics."""

from kubelens.dependencies import check_dependency
from kubelens.models import (
    Evidence,
    Finding,
    ResourceReference,
    serialize_model,
)

MAX_VOLUME_DEPENDENCIES = 20


def extract_volume_dependencies(pod) -> list[dict]:
    """Find required ConfigMap/Secret volumes used by containers."""
    spec = getattr(pod, "spec", None)
    if spec is None:
        return []

    volumes = {
        volume.name: volume
        for volume in (getattr(spec, "volumes", None) or [])
    }

    containers = (
        (getattr(spec, "init_containers", None) or [])
        + (getattr(spec, "containers", None) or [])
    )

    result = []
    seen = set()

    for container in containers:
        for mount in getattr(container, "volume_mounts", None) or []:
            volume = volumes.get(mount.name)
            if volume is None:
                continue

            if getattr(volume, "config_map", None):
                kind = "ConfigMap"
                ref = volume.config_map
            elif getattr(volume, "secret", None):
                kind = "Secret"
                ref = volume.secret
            else:
                continue

            if ref.optional is True:
                continue

            name = (
                ref.name if kind == "ConfigMap"
                else ref.secret_name
            )

            if not name:
                continue

            key = (kind, name, container.name, volume.name)
            if key in seen:
                continue

            seen.add(key)
            result.append({
                "kind": kind,
                "name": name,
                "container": container.name,
                "volume": volume.name,
                "source": "volumeMount",
            })

            if len(result) >= MAX_VOLUME_DEPENDENCIES:
                return result

    return result


def collect_volume_dependencies(api, pod, namespace):
    """Check only referenced resource existence, not content."""
    return [
        check_dependency(api, namespace, dependency)
        for dependency in extract_volume_dependencies(pod)
    ]


def enrich_volume_evidence(payload, report):
    """Create evidence-backed missing-volume findings."""
    for dependency in report.volume_dependencies:
        resource = ResourceReference(
            kind="Pod",
            namespace=report.namespace,
            name=report.pod,
            container=dependency["container"],
        )

        item = Evidence(
            id=f"evidence-{len(payload['evidence']) + 1:03d}",
            source="kubernetes.volume_dependency",
            resource=resource,
            field=(
                f"volume.{dependency['volume']}."
                f"{dependency['kind']}."
                f"{dependency['name']}.availability"
            ),
            value=dependency["availability"],
        )
        payload["evidence"].append(serialize_model(item))

        # Forbidden/unknown cannot be reported as missing.
        if dependency["availability"] != "missing":
            continue

        kind = dependency["kind"]

        finding = Finding(
            id=f"finding-{len(payload['findings']) + 1:03d}",
            rule_id=(
                "volume.missing_configmap"
                if kind == "ConfigMap"
                else "volume.missing_secret"
            ),
            classification="confirmed_condition",
            severity="high",
            summary=(
                f"Required {kind} '{dependency['name']}' "
                f"for volume '{dependency['volume']}' is missing"
            ),
            resource=resource,
            evidence_refs=[item.id],
            recommendations=[
                f"Verify and restore the required {kind} "
                "in the Pod namespace."
            ],
        )
        payload["findings"].append(serialize_model(finding))

    # FailedMount Events are historical observations;
    # they do not necessarily describe the current Pod state.
    event_by_id = {
        event["id"]: event
        for event in payload.get("events", [])
    }

    mount_event_refs = [
        evidence["id"]
        for evidence in payload["evidence"]
        if evidence.get("event_ref") in event_by_id
        and event_by_id[evidence["event_ref"]]["reason"]
        == "FailedMount"
        and evidence["field"] == "event.reason"
    ]

    if mount_event_refs:
        resource = ResourceReference(
            kind="Pod",
            namespace=report.namespace,
            name=report.pod,
        )

        finding = Finding(
            id=f"finding-{len(payload['findings']) + 1:03d}",
            rule_id="pod.failed_mount_event",
            classification="observed_symptom",
            severity="high",
            summary="Kubernetes recorded a FailedMount event",
            resource=resource,
            evidence_refs=mount_event_refs,
            recommendations=[
                "Inspect the volume definitions, mount Events, "
                "and required resources."
            ],
        )
        payload["findings"].append(serialize_model(finding))

    payload["analysis_status"] = (
        "findings_detected"
        if payload["findings"]
        else "no_known_findings"
    )

    payload["limitations"].append(
        "Volume checks currently cover mounted ConfigMap/Secret "
        "resources; projected volumes, PVCs, and CSI are not evaluated."
    )

    return payload
