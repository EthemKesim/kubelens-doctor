"""Normalize bounded Kubernetes Event observations."""

from datetime import datetime, timezone


def normalize_timestamp(value: str | None) -> str | None:
    """Convert valid timestamps to timezone-aware UTC strings."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None

    if parsed.tzinfo is None:
        # Do not guess the timezone of a naive timestamp.
        return None

    return parsed.astimezone(timezone.utc).isoformat()


def normalize_events(records: list[dict]) -> list[dict]:
    """Produce bounded, chronologically ordered Event records."""
    prepared = []

    for original_index, record in enumerate(records[:50]):
        reason = record.get("reason")
        if not reason:
            continue

        timestamp = normalize_timestamp(record.get("timestamp"))

        prepared.append({
            "_order": original_index,
            "reason": str(reason)[:100],
            "type": str(record.get("type") or "Unknown")[:30],
            "timestamp": timestamp,
        })

    # Known timestamps first, unknown timestamps last.
    # Stable ordering preserves input order for equal timestamps.
    prepared.sort(
        key=lambda event: (
            event["timestamp"] is None,
            event["timestamp"] or "",
            event["_order"],
        )
    )

    normalized = []

    for index, event in enumerate(prepared, start=1):
        normalized.append({
            "id": f"event-{index:03d}",
            "reason": event["reason"],
            "type": event["type"],
            "timestamp": event["timestamp"],
        })

    return normalized
