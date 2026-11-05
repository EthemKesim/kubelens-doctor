"""CLI reliability and backward-compatibility tests."""

import json
import sys
from unittest.mock import patch

import pytest
from kubernetes.client.exceptions import ApiException

from kubelens import cli
from kubelens.diagnostics import DiagnosticReport


def run_cli(monkeypatch, arguments):
    """Invoke the CLI without starting a subprocess."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["kubelens", *arguments],
    )
    cli.main()


def make_report():
    """Return an isolated diagnostic report."""
    return DiagnosticReport(
        pod="oom-demo",
        namespace="kubelens-lab",
        context="kind-kubelens-local",
        containers=[
            {
                "name": "memory-app",
                "restart_count": 0,
                "waiting_reason": None,
                "termination_reason": "OOMKilled",
                "exit_code": 137,
                "previous_termination_reason": None,
                "previous_exit_code": None,
            }
        ],
    )


def test_scan_forbidden_error_is_safe(
    monkeypatch, capsys
):
    with patch.object(
        cli,
        "scan_pods",
        side_effect=ApiException(
            status=403,
            reason="SECRET_INTERNAL_DETAILS",
        ),
    ):
        with pytest.raises(SystemExit) as exc:
            run_cli(
                monkeypatch,
                [
                    "scan",
                    "--context",
                    "kind-kubelens-local",
                ],
            )

    output = capsys.readouterr()

    assert exc.value.code == 1
    assert "HTTP 403" in output.err
    assert "RBAC" in output.err
    assert "SECRET_INTERNAL_DETAILS" not in output.err
    assert "Traceback" not in output.err


def test_diagnose_not_found_error(
    monkeypatch, capsys
):
    with patch.object(
        cli,
        "diagnose_pod",
        side_effect=ApiException(status=404),
    ):
        with pytest.raises(SystemExit) as exc:
            run_cli(
                monkeypatch,
                [
                    "diagnose",
                    "--context",
                    "kind-kubelens-local",
                    "--pod",
                    "missing-pod",
                ],
            )

    output = capsys.readouterr()

    assert exc.value.code == 1
    assert "HTTP 404" in output.err
    assert "Traceback" not in output.err


def test_legacy_json_format_remains_compatible(
    monkeypatch, capsys
):
    with patch.object(
        cli,
        "diagnose_pod",
        return_value=make_report(),
    ):
        run_cli(
            monkeypatch,
            [
                "diagnose",
                "--context",
                "kind-kubelens-local",
                "--namespace",
                "kubelens-lab",
                "--pod",
                "oom-demo",
                "--format",
                "json",
            ],
        )

    result = json.loads(capsys.readouterr().out)

    assert result["schema_version"] == "1.0"
    assert result["pod"] == "oom-demo"
    assert isinstance(result["findings"], list)
    assert isinstance(result["containers"], list)


def test_structured_json_links_valid_evidence(
    monkeypatch, capsys
):
    with patch.object(
        cli,
        "diagnose_pod",
        return_value=make_report(),
    ):
        run_cli(
            monkeypatch,
            [
                "diagnose",
                "--context",
                "kind-kubelens-local",
                "--namespace",
                "kubelens-lab",
                "--pod",
                "oom-demo",
                "--format",
                "structured-json",
            ],
        )

    result = json.loads(capsys.readouterr().out)

    assert result["schema_version"] == "2.0"
    assert result["findings"]

    evidence_ids = {
        item["id"] for item in result["evidence"]
    }

    for finding in result["findings"]:
        assert finding["evidence_refs"]
        assert set(finding["evidence_refs"]).issubset(
            evidence_ids
        )
