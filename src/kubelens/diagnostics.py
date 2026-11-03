"""Evidence-based, read-only Kubernetes Pod diagnostics."""

from dataclasses import dataclass, field

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


@dataclass
class DiagnosticReport:
    pod: str
    namespace: str
    context: str
    findings: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)


def analyze_container(container, report: DiagnosticReport):
    """Analyze current and previous container states."""

    name = container.name
    state = container.state
    last_state = container.last_state
    restarts = container.restart_count or 0

    report.evidence.append(
        f"Container {name}: restart count = {restarts}"
    )

    waiting = state.waiting if state else None
    terminated = state.terminated if state else None
    previous = last_state.terminated if last_state else None

    if waiting and waiting.reason:
        report.evidence.append(
            f"Current waiting reason: {waiting.reason}"
        )

        if waiting.message:
            report.evidence.append(
                f"Waiting message: {waiting.message[:300]}"
            )

        if waiting.reason == "CrashLoopBackOff":
            report.findings.append(
                f"{name}: repeated container startup failures"
            )
            report.recommendations.append(
                "Inspect previous container logs and exit codes."
            )

        elif waiting.reason in (
            "ImagePullBackOff",
            "ErrImagePull",
        ):
            report.findings.append(
                f"{name}: container image could not be pulled"
            )
            report.recommendations.append(
                "Verify image name, tag, registry access, "
                "and imagePullSecrets."
            )

    if terminated:
        report.evidence.append(
            f"Termination: {terminated.reason or 'Unknown'}, "
            f"exit code {terminated.exit_code}"
        )

        if terminated.reason == "OOMKilled":
            report.findings.append(
                f"{name}: container terminated due to OOM"
            )
            report.recommendations.append(
                "Inspect memory limits, application memory "
                "usage, and possible memory leaks."
            )

    if previous:
        report.evidence.append(
            f"Previous termination: "
            f"{previous.reason or 'Unknown'}, "
            f"exit code {previous.exit_code}"
        )

        if previous.reason == "OOMKilled":
            report.findings.append(
                f"{name}: previous container was OOMKilled"
            )
            report.recommendations.append(
                "Investigate memory usage before increasing limits."
            )


def diagnose_pod(
    context: str,
    namespace: str,
    pod_name: str,
    include_logs: bool = False,
) -> DiagnosticReport:
    """Collect evidence and apply deterministic diagnostic rules."""

    config.load_kube_config(context=context)
    api = client.CoreV1Api()

    pod = api.read_namespaced_pod(
        name=pod_name,
        namespace=namespace,
    )

    report = DiagnosticReport(
        pod=pod_name,
        namespace=namespace,
        context=context,
    )

    report.evidence.append(
        f"Pod phase: {pod.status.phase or 'Unknown'}"
    )

    containers = (
        (pod.status.init_container_statuses or [])
        + (pod.status.container_statuses or [])
    )

    for container in containers:
        analyze_container(container, report)

    # Fetch Kubernetes Events associated with this Pod.
    try:
        result = api.list_namespaced_event(
            namespace=namespace,
            field_selector=(
                f"involvedObject.kind=Pod,"
                f"involvedObject.name={pod_name}"
            ),
        )

        for event in result.items[-10:]:
            report.events.append(
                f"{event.type or 'Unknown'} | "
                f"{event.reason or 'Unknown'} | "
                f"{(event.message or '')[:300]}"
            )

    except ApiException as exc:
        report.evidence.append(
            f"Events unavailable: HTTP {exc.status}"
        )

    # Logs are opt-in because application logs may contain secrets.
    if include_logs:
        for container in containers:
            try:
                state = container.state
                previous = container.last_state

                use_previous = bool(
                    previous
                    and previous.terminated
                    and state
                    and state.waiting
                )

                log_text = api.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    container=container.name,
                    previous=use_previous,
                    tail_lines=20,
                    limit_bytes=4096,
                )

                report.logs.append(
                    f"[{container.name}] "
                    f"({'previous' if use_previous else 'current'})\n"
                    f"{log_text}"
                )

            except ApiException as exc:
                report.logs.append(
                    f"[{container.name}] Logs unavailable: "
                    f"HTTP {exc.status}"
                )

    if not report.findings:
        report.findings.append(
            "No known failure pattern detected by current rules."
        )
        report.recommendations.append(
            "Review Pod conditions, Events, and application logs "
            "if problems persist."
        )

    return report
