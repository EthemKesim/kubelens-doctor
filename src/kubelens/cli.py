"""Command-line interface for KubeLens Doctor."""

import argparse
import sys

from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException

from kubelens.scanner import scan_pods
from kubelens.diagnostics import diagnose_pod
from kubelens.reporting import report_to_json


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
        help="List Pods in a Kubernetes namespace",
    )
    scan_parser.add_argument("--context", required=True)
    scan_parser.add_argument("--namespace", default="default")

    diagnose_parser = commands.add_parser(
        "diagnose",
        help="Investigate a Pod using Kubernetes evidence",
    )
    diagnose_parser.add_argument("--context", required=True)
    diagnose_parser.add_argument("--namespace", default="default")
    diagnose_parser.add_argument("--pod", required=True)
    diagnose_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    diagnose_parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Display up to 20 log lines per container (may be sensitive)",
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
            print(
                f"{pod.name:<48} "
                f"{pod.status:<24} "
                f"{pod.restarts}"
            )

            if (
                pod.status not in ("Running", "Succeeded")
                or pod.restarts > 0
            ):
                warnings += 1

        print(f"\nScanned: {len(pods)} Pods")
        print(f"Potential warnings: {warnings}")

    elif args.command == "diagnose":
        try:
            report = diagnose_pod(
                context=args.context,
                namespace=args.namespace,
                pod_name=args.pod,
                include_logs=args.include_logs,
            )
        except (ApiException, ConfigException, OSError) as exc:
            print(f"Diagnosis failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        if args.format == "json":
            print(report_to_json(report))
            return

        print("\n=== KUBELENS DIAGNOSTIC REPORT ===")
        print(f"Context: {report.context}")
        print(f"Namespace: {report.namespace}")
        print(f"Pod: {report.pod}")

        print("\nFINDINGS")
        for item in report.findings:
            print(f"  - {item}")

        print("\nEVIDENCE")
        for item in report.evidence:
            print(f"  - {item}")

        print("\nKUBERNETES EVENTS")
        for item in report.events:
            print(f"  - {item}")
        if not report.events:
            print("  No Events returned.")

        if args.include_logs:
            print("\nCONTAINER LOGS (potentially sensitive)")
            for item in report.logs:
                print(item)
            if not report.logs:
                print("  No container logs returned.")

        print("\nRECOMMENDED INVESTIGATION")
        for item in report.recommendations:
            print(f"  - {item}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
