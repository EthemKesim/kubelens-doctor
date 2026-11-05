"""Tests for Pod condition and Event evidence correlation."""

from kubelens.diagnostics import DiagnosticReport
from kubelens.structured import build_structured_report
from kubelens.reporting import report_to_json
import json


def make_report(conditions=None, events=None):
    return DiagnosticReport(
        pod="pending-demo",
        namespace="kubelens-lab",
        context="kind-kubelens-local",
        conditions=conditions or [],
        event_records=events or [],
    )


def test_unschedulable_condition_creates_finding():
    report = make_report(
        conditions=[{
            "type": "PodScheduled",
            "status": "False",
            "reason": "Unschedulable",
        }],
    )

    result = build_structured_report(report)

    assert len(result["findings"]) == 1
    assert result["findings"][0]["rule_id"] == "pod.unschedulable"
    assert result["findings"][0]["classification"] == "confirmed_condition"


def test_event_correlates_with_unschedulable_finding():
    report = make_report(
        conditions=[{
            "type": "PodScheduled",
            "status": "False",
            "reason": "Unschedulable",
        }],
        events=[{
            "reason": "FailedScheduling",
            "type": "Warning",
            "timestamp": "2026-11-05T10:00:00+00:00",
        }],
    )

    result = build_structured_report(report)
    finding = result["findings"][0]
    by_id = {item["id"]: item for item in result["evidence"]}

    assert any(
        by_id[ref]["source"] == "kubernetes.event"
        and by_id[ref]["value"] == "FailedScheduling"
        for ref in finding["evidence_refs"]
    )


def test_event_alone_does_not_confirm_current_failure():
    report = make_report(
        events=[{
            "reason": "FailedScheduling",
            "type": "Warning",
            "timestamp": None,
        }],
    )

    result = build_structured_report(report)

    assert result["findings"] == []
    assert any(
        item["value"] == "FailedScheduling"
        for item in result["evidence"]
    )


def test_ready_pod_does_not_create_scheduling_failure():
    report = make_report(
        conditions=[{
            "type": "PodScheduled",
            "status": "True",
            "reason": None,
        }],
    )

    result = build_structured_report(report)

    assert result["findings"] == []
    assert result["evidence"]


def test_legacy_json_does_not_expose_new_internal_fields():
    report = make_report(
        conditions=[{
            "type": "PodScheduled",
            "status": "False",
            "reason": "Unschedulable",
        }],
        events=[{
            "reason": "FailedScheduling",
            "type": "Warning",
            "timestamp": None,
        }],
    )

    result = json.loads(report_to_json(report))

    assert result["schema_version"] == "1.0"
    assert "conditions" not in result
    assert "event_records" not in result
