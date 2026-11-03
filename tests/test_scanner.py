"""Unit tests for Kubernetes Pod discovery."""

from types import SimpleNamespace
from unittest.mock import patch

from kubelens.scanner import describe_pod, scan_pods


def make_pod(phase="Running", reason=None, restarts=0):
    state = SimpleNamespace(
        waiting=SimpleNamespace(reason=reason) if reason else None,
        terminated=None,
    )

    container = SimpleNamespace(
        restart_count=restarts,
        state=state,
    )

    return SimpleNamespace(
        metadata=SimpleNamespace(
            name="test-api",
            namespace="demo",
        ),
        status=SimpleNamespace(
            phase=phase,
            init_container_statuses=[],
            container_statuses=[container],
        ),
    )


def test_running_pod():
    result = describe_pod(make_pod())

    assert result.name == "test-api"
    assert result.status == "Running"
    assert result.restarts == 0


def test_crashloop_pod():
    result = describe_pod(
        make_pod(reason="CrashLoopBackOff", restarts=5)
    )

    assert result.status == "CrashLoopBackOff"
    assert result.restarts == 5


def test_pending_pod():
    result = describe_pod(make_pod(phase="Pending"))

    assert result.status == "Pending"


@patch("kubelens.scanner.client.CoreV1Api")
@patch("kubelens.scanner.config.load_kube_config")
def test_scan_uses_explicit_context(mock_config, mock_api):
    mock_api.return_value.list_namespaced_pod.return_value.items = [
        make_pod()
    ]

    result = scan_pods("kind-kubelens-local", "demo")

    mock_config.assert_called_once_with(
        context="kind-kubelens-local"
    )
    mock_api.return_value.list_namespaced_pod.assert_called_once_with(
        namespace="demo"
    )

    assert len(result) == 1
    assert result[0].name == "test-api"
