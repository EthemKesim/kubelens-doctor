"""Tests for evidence-linked diagnostic reports."""

from kubelens.diagnostics import DiagnosticReport
from kubelens.structured import build_structured_report


def make_report(containers):
    return DiagnosticReport(
        pod="demo",
        namespace="kubelens-lab",
        context="kind-kubelens-local",
        containers=containers,
    )


def make_container(
    name="app",
    waiting=None,
    terminated=None,
    previous=None,
    exit_code=None,
):
    return {
        "name": name,
        "restart_count": 2,
        "waiting_reason": waiting,
        "termination_reason": terminated,
        "exit_code": exit_code,
        "previous_termination_reason": previous,
        "previous_exit_code": 1 if previous else None,
    }


def test_oom_finding_has_traceable_evidence():
    report = make_report([
        make_container(terminated="OOMKilled", exit_code=137)
    ])

    result = build_structured_report(report)

    finding = result["findings"][0]
    evidence_ids = {e["id"] for e in result["evidence"]}

    assert finding["rule_id"] == "container.oom_killed"
    assert finding["classification"] == "confirmed_condition"
    assert set(finding["evidence_refs"]).issubset(evidence_ids)
    assert any(
        e["field"] == "exit_code" and e["value"] == 137
        for e in result["evidence"]
    )


def test_crashloop_is_a_symptom_not_confirmed_root_cause():
    report = make_report([
        make_container(waiting="CrashLoopBackOff")
    ])

    finding = build_structured_report(report)["findings"][0]

    assert finding["classification"] == "observed_symptom"
    assert finding["rule_id"] == "container.crash_loop"


def test_multiple_containers_keep_separate_references():
    report = make_report([
        make_container(name="api", waiting="CrashLoopBackOff"),
        make_container(name="sidecar", terminated="OOMKilled"),
    ])

    result = build_structured_report(report)

    assert len(result["findings"]) == 2
    assert {
        f["resource"]["container"] for f in result["findings"]
    } == {"api", "sidecar"}

    for finding in result["findings"]:
        for ref in finding["evidence_refs"]:
            item = next(
                e for e in result["evidence"] if e["id"] == ref
            )
            assert (
                item["resource"]["container"]
                == finding["resource"]["container"]
            )


def test_unknown_failure_does_not_invent_diagnosis():
    report = make_report([
        make_container(waiting="ContainerCreating")
    ])

    result = build_structured_report(report)

    assert result["findings"] == []
    assert result["analysis_status"] == "no_known_findings"


def test_report_schema_is_versioned():
    result = build_structured_report(make_report([]))

    assert result["schema_version"] == "2.0"
    assert result["limitations"]


def test_previous_oom_is_linked_to_previous_state():
    report = make_report([
        make_container(
            waiting="CrashLoopBackOff",
            previous="OOMKilled",
        )
    ])

    result = build_structured_report(report)

    assert len(result["findings"]) == 2
    assert any(
        e["field"] == "previous_termination_reason"
        and e["value"] == "OOMKilled"
        for e in result["evidence"]
    )


def test_previous_error_detected_without_current_crashloop():
    report = make_report([
        make_container(previous="Error")
    ])

    result = build_structured_report(report)

    assert len(result["findings"]) == 1
    assert result["findings"][0]["rule_id"] == (
        "container.previous_failure"
    )
    assert result["findings"][0]["classification"] == (
        "observed_symptom"
    )


def test_unknown_state_still_retains_observations():
    report = make_report([
        make_container(waiting="ContainerCreating")
    ])

    result = build_structured_report(report)

    assert result["findings"] == []
    assert any(
        item["field"] == "waiting_reason"
        and item["value"] == "ContainerCreating"
        for item in result["evidence"]
    )


def test_previous_failure_links_to_real_evidence():
    report = make_report([
        make_container(previous="Error")
    ])

    result = build_structured_report(report)
    finding = result["findings"][0]

    evidence_by_id = {
        item["id"]: item for item in result["evidence"]
    }

    assert all(
        ref in evidence_by_id
        for ref in finding["evidence_refs"]
    )

    assert any(
        evidence_by_id[ref]["field"]
        == "previous_termination_reason"
        for ref in finding["evidence_refs"]
    )
