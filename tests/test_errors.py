"""Tests for safe Kubernetes API error handling."""

from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import MaxRetryError

from kubelens.errors import format_kubernetes_error


def test_forbidden_error_is_actionable_and_safe():
    exc = ApiException(
        status=403,
        reason="Sensitive API response",
    )

    message = format_kubernetes_error(
        exc, "kind-kubelens-local"
    )

    assert "HTTP 403" in message
    assert "RBAC" in message
    assert "Sensitive API response" not in message


def test_not_found_error():
    exc = ApiException(status=404)

    message = format_kubernetes_error(exc, "test-context")

    assert "HTTP 404" in message
    assert "resource name" in message.lower()


def test_connection_failure():
    exc = MaxRetryError(
        pool=None,
        url="/api/v1/pods",
        reason=ConnectionError("Connection refused"),
    )

    message = format_kubernetes_error(exc, "kind-kubelens-local")

    assert "Cannot communicate" in message
    assert "kind-kubelens-local" in message
    assert "/api/v1/pods" not in message


def test_authentication_failure():
    exc = ApiException(status=401)

    message = format_kubernetes_error(exc, "test-context")

    assert "HTTP 401" in message
    assert "kubeconfig" in message


def test_unknown_api_error():
    exc = ApiException(status=503)

    message = format_kubernetes_error(exc, "test-context")

    assert "HTTP 503" in message
