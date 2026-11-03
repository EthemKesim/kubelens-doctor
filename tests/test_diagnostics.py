"""Tests for evidence-based container diagnostics."""

from types import SimpleNamespace

from kubelens.diagnostics import (
    DiagnosticReport,
    analyze_container,
)


def make_container(
    waiting=None,
    terminated=None,
    previous=None,
    restarts=0,
):
    return SimpleNamespace(
        name="test-container",
        restart_count=restarts,
        state=SimpleNamespace(
            waiting=(
                SimpleNamespace(reason=waiting, message=None)
                if waiting else None
            ),
            terminated=(
                SimpleNamespace(
                    reason=terminated,
                    exit_code=137,
                )
                if terminated else None
            ),
        ),
        last_state=SimpleNamespace(
            terminated=(
                SimpleNamespace(
                    reason=previous,
                    exit_code=1,
                )
                if previous else None
            ),
        ),
    )


def make_report():
    return DiagnosticReport(
        pod="test-pod",
        namespace="kubelens-lab",
        context="kind-kubelens-local",
    )


def test_crashloop_diagnosis():
    report = make_report()

    analyze_container(
        make_container(
            waiting="CrashLoopBackOff",
            previous="Error",
            restarts=5,
        ),
        report,
    )

    assert any(
        "startup failures" in finding
        for finding in report.findings
    )
    assert any(
        "exit code 1" in item
        for item in report.evidence
    )


def test_oom_diagnosis():
    report = make_report()

    analyze_container(
        make_container(terminated="OOMKilled"),
        report,
    )

    assert any(
        "due to OOM" in finding
        for finding in report.findings
    )


def test_image_pull_diagnosis():
    report = make_report()

    analyze_container(
        make_container(waiting="ImagePullBackOff"),
        report,
    )

    assert any(
        "image could not be pulled" in finding
        for finding in report.findings
    )


def test_previous_oom_diagnosis():
    report = make_report()

    analyze_container(
        make_container(
            waiting="CrashLoopBackOff",
            previous="OOMKilled",
            restarts=3,
        ),
        report,
    )

    assert any(
        "previous container was OOMKilled" in finding
        for finding in report.findings
    )
