"""Read-only checks for Kubernetes configuration dependencies."""

from kubernetes.client.exceptions import ApiException

METADATA_ACCEPT = (
    "application/json;"
    "as=PartialObjectMetadata;"
    "g=meta.k8s.io;v=v1"
)

MAX_DEPENDENCIES = 20


def extract_dependencies(pod) -> list[dict]:
    """Extract required ConfigMap and Secret references from Pod spec."""
    dependencies = []
    seen = set()

    containers = (
        (pod.spec.init_containers or [])
        + (pod.spec.containers or [])
    )

    def add(kind, name, container, source, optional=False):
        if not name or optional:
            return

        key = (kind, name, container, source)
        if key in seen:
            return

        seen.add(key)
        dependencies.append({
            "kind": kind,
            "name": name,
            "container": container,
            "source": source,
        })

    for container in containers:
        for entry in container.env_from or []:
            config = entry.config_map_ref
            secret = entry.secret_ref

            if config:
                add(
                    "ConfigMap",
                    config.name,
                    container.name,
                    "envFrom",
                    config.optional,
                )

            if secret:
                add(
                    "Secret",
                    secret.name,
                    container.name,
                    "envFrom",
                    secret.optional,
                )

        for variable in container.env or []:
            source = variable.value_from
            if source is None:
                continue

            if source.config_map_key_ref:
                ref = source.config_map_key_ref
                add(
                    "ConfigMap",
                    ref.name,
                    container.name,
                    "env.valueFrom",
                    ref.optional,
                )

            if source.secret_key_ref:
                ref = source.secret_key_ref
                add(
                    "Secret",
                    ref.name,
                    container.name,
                    "env.valueFrom",
                    ref.optional,
                )

    return dependencies[:MAX_DEPENDENCIES]


def check_dependency(api, namespace: str, dependency: dict) -> dict:
    """Check existence through metadata-only Kubernetes responses."""
    result = dict(dependency)

    try:
        options = {
            "name": dependency["name"],
            "namespace": namespace,
            "_headers": {"Accept": METADATA_ACCEPT},
            "_request_timeout": 5,
        }

        if dependency["kind"] == "ConfigMap":
            api.read_namespaced_config_map(**options)
        else:
            api.read_namespaced_secret(**options)

        result["availability"] = "present"

    except ApiException as exc:
        result["availability"] = {
            404: "missing",
            401: "unauthorized",
            403: "forbidden",
            406: "metadata_unsupported",
        }.get(exc.status, "unknown")

    return result


def collect_dependencies(api, pod, namespace: str) -> list[dict]:
    """Collect bounded dependency statuses without reading values."""
    return [
        check_dependency(api, namespace, dependency)
        for dependency in extract_dependencies(pod)
    ]
