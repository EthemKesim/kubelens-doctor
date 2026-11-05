"""Safe and actionable Kubernetes API error messages."""

from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError


def format_kubernetes_error(exc: Exception, context: str) -> str:
    """Return a useful error without exposing raw API responses."""

    prefix = f"KubeLens Doctor: Kubernetes request failed\nContext: {context}"

    if isinstance(exc, ApiException):
        if exc.status == 403:
            return (
                f"{prefix}\n"
                "Reason: Access denied (HTTP 403).\n"
                "Check RBAC permissions for the requested resource and verb."
            )

        if exc.status == 404:
            return (
                f"{prefix}\n"
                "Reason: Resource not found (HTTP 404).\n"
                "Check the resource name and namespace."
            )

        if exc.status in (401,):
            return (
                f"{prefix}\n"
                "Reason: Authentication failed (HTTP 401).\n"
                "Check kubeconfig credentials."
            )

        if exc.status == 429:
            return (
                f"{prefix}\n"
                "Reason: API rate limit exceeded (HTTP 429).\n"
                "Reduce request frequency and retry later."
            )

        return (
            f"{prefix}\n"
            f"Reason: Kubernetes API returned HTTP {exc.status}."
        )

    if isinstance(exc, (HTTPError, OSError)):
        return (
            f"{prefix}\n"
            "Reason: Cannot communicate with the Kubernetes API.\n"
            "Check Docker, cluster availability, and network connectivity."
        )

    return (
        f"{prefix}\n"
        "Reason: Kubernetes configuration could not be loaded.\n"
        "Check the selected context and kubeconfig."
    )
