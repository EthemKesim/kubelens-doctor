"""Tests for normalized Kubernetes Event records."""

from kubelens.diagnostics import DiagnosticReport
from kubelens.event_records import normalize_events
from kubelens.structured import build_structured_report


def test_events_sorted_chronologically():
    records = [
        {
            "reason": "BackOff",
            "type": "Warning",
            "timestamp": "2026-11-05T12:00:00+00:00",
        },
        {
            "reason": "Started",
            "type": "Normal",
            "timestamp": "2026-11-05T10:00:00+00:00",
        },
    ]

    result = normalize_events(records)

    assert [item["reason"] for item in result] == [
        "Started",
        "BackOff",
    ]


def test_timezone_normalization():
    result = normalize_events([{
        "reason": "Failed",
        "type": "Warning",
        "timestamp": "2026-11-05T12:00:00+02:00",
    }])

    assert result[0]["timestamp"] == (
        "2026-11-05T10:00:00+00:00"
    )


def test_missing_timestamp_is_not_invented():
    result = normalize_events([
        {
            "reason": "UnknownTime",
            "timestamp": None,
        },
        {
            "reason": "KnownTime",
            "timestamp": "2026-11-05T10:00:00Z",
        },
    ])

    assert result[0]["reason"] == "KnownTime"
    assert result[1]["timestamp"] is None


def test_repeated_event_reasons_remain_separate():
    result = normalize_events([
        {"reason": "Failed", "timestamp": None},
        {"reason": "Failed", "timestamp": None},
    ])

    assert len(result) == 2
    assert result[0]["id"] != result[1]["id"]


def test_event_evidence_references_correct_record():
    report = DiagnosticReport(
        pod="unschedulable-demo",
        namespace="kubelens-lab",
        context="kind-kubelens-local",
        conditions=[{
            "type": "PodScheduled",
            "status": "False",
            "reason": "Unschedulable",
        }],
        event_records=[{
            "reason": "FailedScheduling",
            "type": "Warning",
            "timestamp": "2026-11-05T10:00:00Z",
        }],
    )

    payload = build_structured_report(report)

    event_ids = {item["id"] for item in payload["events"]}
    evidence_by_id = {
        item["id"]: item for item in payload["evidence"]
    }

    finding = next(
        item for item in payload["findings"]
        if item["rule_id"] == "pod.unschedulable"
    )

    linked_events = [
        evidence_by_id[ref]["event_ref"]
        for ref in finding["evidence_refs"]
        if "event_ref" in evidence_by_id[ref]
    ]

    assert linked_events
    assert set(linked_events).issubset(event_ids)


def test_event_collection_is_bounded():
    records = [
        {"reason": "BackOff", "timestamp": None}
        for _ in range(100)
    ]

    result = normalize_events(records)

    assert len(result) == 50
