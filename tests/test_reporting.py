"""Tests for structured reporting and Event correlation."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from kubelens.diagnostics import DiagnosticReport
from kubelens.events import correlate_events
from kubelens.reporting import report_to_json


def make_event(uid, minute):
    return SimpleNamespace(
        involved_object=SimpleNamespace(uid=uid),
        event_time=datetime(
            2026, 11, 3, 12, minute,
            tzinfo=timezone.utc,
        ),
    )


def test_events_match_pod_uid():
    events = [
        make_event("old-pod-uid", 1),
        make_event("correct-uid", 2),
    ]

    result = correlate_events(events, "correct-uid")

    assert len(result) == 1
    assert result[0].involved_object.uid == "correct-uid"


def test_events_are_chronological():
    events = [
        make_event("pod-1", 10),
        make_event("pod-1", 2),
        make_event("pod-1", 5),
    ]

    result = correlate_events(events, "pod-1")

    assert [
        event.event_time.minute for event in result
    ] == [2, 5, 10]


def test_missing_uid_returns_no_events():
    result = correlate_events(
        [make_event("pod-1", 1)],
        "",
    )

    assert result == []


def test_report_serializes_as_json():
    report = DiagnosticReport(
        pod="oom-demo",
        namespace="kubelens-lab",
        context="kind-kubelens-local",
    )

    report.findings.append("Container OOMKilled")
    report.evidence.append("Exit code 137")
    report.containers.append({
        "name": "memory-app",
        "termination_reason": "OOMKilled",
    })

    data = json.loads(report_to_json(report))

    assert data["schema_version"] == "1.0"
    assert data["pod"] == "oom-demo"
    assert data["findings"] == ["Container OOMKilled"]
    assert data["containers"][0]["termination_reason"] == "OOMKilled"
