"""Evidence-based, read-only Kubernetes Pod diagnostics."""

from dataclasses import dataclass, field

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from kubelens.events import correlate_events, event_timestamp
from kubelens.dependencies import collect_dependencies
from kubelens.volume_diagnostics import collect_volume_dependencies


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
    containers: list[dict] = field(default_factory=list)
    conditions: list[dict] = field(default_factory=list)
    event_records: list[dict] = field(default_factory=list)
    dependencies: list[dict] = field(default_factory=list)
    volume_dependencies: list[dict] = field(default_factory=list)


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

    report.containers.append({
        "name": name,
        "restart_count": restarts,
        "waiting_reason": waiting.reason if waiting else None,
        "termination_reason": (
            terminated.reason if terminated else None
        ),
        "exit_code": (
            terminated.exit_code if terminated else None
        ),
        "previous_termination_reason": (
            previous.reason if previous else None
        ),
        "previous_exit_code": (
            previous.exit_code if previous else None
        ),
    })

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

    # Capture conditions without copying their free-text messages.
    for condition in pod.status.conditions or []:
        report.conditions.append({
            "type": condition.type,
            "status": condition.status,
            "reason": condition.reason,
        })

    containers = (
        (pod.status.init_container_statuses or [])
        + (pod.status.container_statuses or [])
    )

    for container in containers:
        analyze_container(container, report)

    # Inspect referenced resources without reading configuration values.
    report.dependencies = collect_dependencies(api, pod, namespace)
    report.volume_dependencies = collect_volume_dependencies(
        api, pod, namespace
    )

    # Fetch Events by UID to avoid mixing old and new Pods.
    pod_uid = getattr(pod.metadata, "uid", None)

    if pod_uid:
        try:
            result = api.list_namespaced_event(
                namespace=namespace,
                field_selector=f"involvedObject.uid={pod_uid}",
            )

            matched = correlate_events(result.items, pod_uid)

            for event in matched[-10:]:
                timestamp = event_timestamp(event)
                report.event_records.append({
                    "reason": event.reason,
                    "type": event.type,
                    "timestamp": (
                        timestamp.isoformat()
                        if timestamp else None
                    ),
                })

                timestamp = event_timestamp(event)
                time_label = (
                    timestamp.isoformat()
                    if timestamp else "Unknown time"
                )

                report.events.append(
                    f"{time_label} | "
                    f"{event.type or 'Unknown'} | "
                    f"{event.reason or 'Unknown'} | "
                    f"{(event.message or '')[:300]}"
                )

        except ApiException as exc:
            report.evidence.append(
                f"Events unavailable: HTTP {exc.status}"
            )
    else:
        report.evidence.append(
            "Events unavailable: Pod UID missing."
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
