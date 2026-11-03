"""Read-only Kubernetes Pod discovery."""

from dataclasses import dataclass

from kubernetes import client, config


@dataclass(frozen=True)
class PodInfo:
    name: str
    namespace: str
    status: str
    restarts: int


def describe_pod(pod) -> PodInfo:
    """Convert a Kubernetes Pod into a simple diagnostic record."""
    metadata = pod.metadata
    pod_status = pod.status

    status = pod_status.phase or "Unknown"
    restarts = 0

    container_statuses = (
        (pod_status.init_container_statuses or [])
        + (pod_status.container_statuses or [])
    )

    for container in container_statuses:
        restarts += container.restart_count or 0

        if container.state and container.state.waiting:
            reason = container.state.waiting.reason
            if reason and reason != "ContainerCreating":
                status = reason

        if container.state and container.state.terminated:
            reason = container.state.terminated.reason
            if reason and status not in ("Running", "Succeeded"):
                status = reason

    return PodInfo(
        name=metadata.name,
        namespace=metadata.namespace,
        status=status,
        restarts=restarts,
    )


def scan_pods(context: str, namespace: str) -> list[PodInfo]:
    """Fetch Pods from an explicitly selected Kubernetes context."""
    config.load_kube_config(context=context)

    api = client.CoreV1Api()
    response = api.list_namespaced_pod(namespace=namespace)

    return [describe_pod(pod) for pod in response.items]
