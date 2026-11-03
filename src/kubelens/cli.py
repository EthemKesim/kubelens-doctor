"""Command-line interface for KubeLens Doctor."""

import argparse


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

    parser.parse_args()


if __name__ == "__main__":
    main()
