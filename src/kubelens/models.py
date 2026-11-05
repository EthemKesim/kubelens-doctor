"""Typed models for traceable diagnostic evidence."""

from dataclasses import asdict, dataclass
from typing import Literal


Classification = Literal[
    "confirmed_condition",
    "observed_symptom",
    "hypothesis",
]

Severity = Literal["info", "low", "medium", "high", "critical"]


@dataclass(frozen=True)
class ResourceReference:
    kind: str
    namespace: str
    name: str
    container: str | None = None


@dataclass(frozen=True)
class Evidence:
    id: str
    source: str
    resource: ResourceReference
    field: str
    value: str | int | None


@dataclass(frozen=True)
class Finding:
    id: str
    rule_id: str
    classification: Classification
    severity: Severity
    summary: str
    resource: ResourceReference
    evidence_refs: list[str]
    recommendations: list[str]


def serialize_model(model) -> dict:
    """Convert a typed model into a JSON-compatible dictionary."""
    return asdict(model)
