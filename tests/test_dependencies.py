"""Tests for safe Kubernetes configuration dependency checks."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

from kubernetes.client.exceptions import ApiException

from kubelens.dependencies import (
    METADATA_ACCEPT,
    check_dependency,
    extract_dependencies,
)
from kubelens.diagnostics import DiagnosticReport
from kubelens.structured import build_structured_report


def make_pod(kind):
    config = NS(name="missing-config", optional=False)

    entry = NS(
        config_map_ref=config if kind == "ConfigMap" else None,
        secret_ref=config if kind == "Secret" else None,
    )

    container = NS(
        name="app",
        env_from=[entry],
        env=[],
    )

    return NS(
        spec=NS(
            init_containers=[],
            containers=[container],
        )
    )


def make_report(kind, availability, waiting="CreateContainerConfigError"):
    return DiagnosticReport(
        pod="demo",
        namespace="kubelens-lab",
        context="kind-kubelens-local",
        containers=[{
            "name": "app",
            "restart_count": 0,
            "waiting_reason": waiting,
        }],
        dependencies=[{
            "kind": kind,
            "name": "missing-config",
            "container": "app",
            "source": "envFrom",
            "availability": availability,
        }],
    )


def test_extract_required_configmap():
    result = extract_dependencies(make_pod("ConfigMap"))

    assert len(result) == 1
    assert result[0]["kind"] == "ConfigMap"
    assert result[0]["container"] == "app"


def test_extract_required_secret():
    result = extract_dependencies(make_pod("Secret"))

    assert len(result) == 1
    assert result[0]["kind"] == "Secret"


def test_missing_configmap_creates_confirmed_finding():
    payload = build_structured_report(
        make_report("ConfigMap", "missing")
    )

    rules = {item["rule_id"] for item in payload["findings"]}

    assert "dependency.missing_configmap" in rules


def test_missing_secret_creates_confirmed_finding():
    payload = build_structured_report(
        make_report("Secret", "missing")
    )

    rules = {item["rule_id"] for item in payload["findings"]}

    assert "dependency.missing_secret" in rules


def test_forbidden_secret_is_not_reported_missing():
    api = Mock()
    api.read_namespaced_secret.side_effect = ApiException(status=403)

    result = check_dependency(
        api,
        "kubelens-lab",
        {
            "kind": "Secret",
            "name": "protected-secret",
            "container": "app",
            "source": "envFrom",
        },
    )

    assert result["availability"] == "forbidden"

    payload = build_structured_report(
        make_report("Secret", "forbidden")
    )

    assert not any(
        item["rule_id"] == "dependency.missing_secret"
        for item in payload["findings"]
    )


def test_secret_request_is_metadata_only():
    api = Mock()

    check_dependency(
        api,
        "kubelens-lab",
        {
            "kind": "Secret",
            "name": "protected-secret",
            "container": "app",
            "source": "envFrom",
        },
    )

    kwargs = api.read_namespaced_secret.call_args.kwargs

    assert kwargs["_headers"]["Accept"] == METADATA_ACCEPT


def test_dependency_finding_has_valid_evidence_references():
    payload = build_structured_report(
        make_report("ConfigMap", "missing")
    )

    evidence_ids = {item["id"] for item in payload["evidence"]}

    finding = next(
        item for item in payload["findings"]
        if item["rule_id"] == "dependency.missing_configmap"
    )

    assert len(finding["evidence_refs"]) == 2
    assert set(finding["evidence_refs"]).issubset(evidence_ids)


def test_missing_resource_without_current_error_is_not_attributed():
    payload = build_structured_report(
        make_report("ConfigMap", "missing", waiting="ContainerCreating")
    )

    assert not any(
        item["rule_id"] == "dependency.missing_configmap"
        for item in payload["findings"]
    )
