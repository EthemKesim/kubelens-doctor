"""Tests for volume dependency and FailedMount diagnostics."""

from types import SimpleNamespace as NS

from kubelens.diagnostics import DiagnosticReport
from kubelens.structured import build_structured_report
from kubelens.volume_diagnostics import extract_volume_dependencies


def pod_with_volume(kind="ConfigMap", optional=False):
    ref = NS(
        name="missing-config" if kind == "ConfigMap" else None,
        secret_name="missing-secret" if kind == "Secret" else None,
        optional=optional,
    )

    volume = NS(
        name="settings",
        config_map=ref if kind == "ConfigMap" else None,
        secret=ref if kind == "Secret" else None,
    )

    container = NS(
        name="app",
        volume_mounts=[NS(name="settings")],
    )

    return NS(spec=NS(
        volumes=[volume],
        init_containers=[],
        containers=[container],
    ))


def report_with_volume(kind, availability, events=None):
    return DiagnosticReport(
        pod="mount-demo",
        namespace="kubelens-lab",
        context="kind-kubelens-local",
        volume_dependencies=[{
            "kind": kind,
            "name": (
                "missing-config"
                if kind == "ConfigMap" else "missing-secret"
            ),
            "container": "app",
            "volume": "settings",
            "source": "volumeMount",
            "availability": availability,
        }],
        event_records=events or [],
    )


def test_configmap_volume_reference():
    result = extract_volume_dependencies(
        pod_with_volume("ConfigMap")
    )

    assert len(result) == 1
    assert result[0]["kind"] == "ConfigMap"
    assert result[0]["volume"] == "settings"


def test_secret_volume_reference():
    result = extract_volume_dependencies(
        pod_with_volume("Secret")
    )

    assert len(result) == 1
    assert result[0]["kind"] == "Secret"


def test_optional_volume_is_not_required():
    result = extract_volume_dependencies(
        pod_with_volume(optional=True)
    )

    assert result == []


def test_missing_configmap_volume_is_confirmed():
    result = build_structured_report(
        report_with_volume("ConfigMap", "missing")
    )

    assert any(
        finding["rule_id"] == "volume.missing_configmap"
        and finding["classification"] == "confirmed_condition"
        for finding in result["findings"]
    )


def test_forbidden_secret_does_not_prove_missing():
    result = build_structured_report(
        report_with_volume("Secret", "forbidden")
    )

    assert not any(
        finding["rule_id"] == "volume.missing_secret"
        for finding in result["findings"]
    )


def test_failed_mount_event_has_valid_evidence():
    result = build_structured_report(
        report_with_volume(
            "ConfigMap",
            "missing",
            events=[{
                "reason": "FailedMount",
                "type": "Warning",
                "timestamp": "2026-11-05T20:00:00Z",
            }],
        )
    )

    finding = next(
        finding for finding in result["findings"]
        if finding["rule_id"] == "pod.failed_mount_event"
    )

    evidence = {
        item["id"]: item for item in result["evidence"]
    }

    assert finding["evidence_refs"]
    assert all(
        ref in evidence for ref in finding["evidence_refs"]
    )


def test_missing_pod_spec_is_safe():
    assert extract_volume_dependencies(NS(spec=None)) == []
