"""Command-line interface for KubeLens Doctor."""

import argparse
import sys

from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException

from kubelens.scanner import scan_pods


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kubelens",
        description="KubeLens Doctor - Kubernetes troubleshooting CLI",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="KubeLens Doctor 0.1.0",
    )

    commands = parser.add_subparsers(dest="command")

    scan_parser = commands.add_parser(
        "scan",
        help="Inspect Pods in a Kubernetes namespace",
    )

    scan_parser.add_argument(
        "--context",
        required=True,
        help="Explicit Kubernetes context",
    )

    scan_parser.add_argument(
        "--namespace",
        default="default",
        help="Namespace to inspect (default: default)",
    )

    args = parser.parse_args()

    if args.command == "scan":
        try:
            pods = scan_pods(args.context, args.namespace)
        except (ApiException, ConfigException, OSError) as exc:
            print(f"Scan failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        print("\nKubeLens Doctor v0.1.0")
        print(f"Context: {args.context}")
        print(f"Namespace: {args.namespace}\n")

        if not pods:
            print("No Pods found in this namespace.")
            return

        print(f"{'POD':<48} {'STATUS':<24} RESTARTS")
        print("-" * 85)

        warnings = 0

        for pod in pods:
            print(f"{pod.name:<48} {pod.status:<24} {pod.restarts}")

            if pod.status not in ("Running", "Succeeded") or pod.restarts > 0:
                warnings += 1

        print(f"\nScanned: {len(pods)} Pods")
        print(f"Potential warnings: {warnings}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
