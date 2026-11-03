"""Structured diagnostic report serialization."""

import json
from dataclasses import asdict


def report_to_json(report) -> str:
    """Serialize a diagnostic report as formatted JSON."""

    payload = asdict(report)
    payload["schema_version"] = "1.0"

    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
    )
