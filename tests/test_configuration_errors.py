"""Regression tests for container configuration diagnostics."""

from kubelens.diagnostics import DiagnosticReport
from kubelens.structured import build_structured_report


def make_report(waiting_reason):
    return DiagnosticReport(
        pod="configuration-demo",
        namespace="kubelens-lab",
        context="kind-kubelens-local",
        containers=[{
            "name": "test-app",
            "restart_count": 0,
            "waiting_reason": waiting_reason,
            "termination_reason": None,
            "exit_code": None,
            "previous_termination_reason": None,
            "previous_exit_code": None,
        }],
    )


def test_configuration_error_detected():
    result = build_structured_report(
        make_report("CreateContainerConfigError")
    )

    assert any(
        item["rule_id"] == "container.configuration_error"
        and item["classification"] == "observed_symptom"
        for item in result["findings"]
    )


def test_configuration_error_has_real_evidence():
    result = build_structured_report(
        make_report("CreateContainerConfigError")
    )

    finding = next(
        item for item in result["findings"]
        if item["rule_id"] == "container.configuration_error"
    )

    evidence = {
        item["id"]: item for item in result["evidence"]
    }

    assert any(
        evidence[ref]["value"] == "CreateContainerConfigError"
        for ref in finding["evidence_refs"]
    )


def test_container_creating_is_not_automatically_failure():
    result = build_structured_report(
        make_report("ContainerCreating")
    )

    assert result["findings"] == []
    assert result["analysis_status"] == "no_known_findings"
