"""Event correlation for Kubernetes Pods."""

from datetime import datetime, timezone


def event_timestamp(event) -> datetime | None:
    """Return the best available event timestamp."""
    metadata = getattr(event, "metadata", None)

    return (
        getattr(event, "event_time", None)
        or getattr(event, "last_timestamp", None)
        or getattr(event, "first_timestamp", None)
        or getattr(metadata, "creation_timestamp", None)
    )


def correlate_events(events, pod_uid: str) -> list:
    """Keep events for one Pod instance, ordered by time."""

    if not pod_uid:
        return []

    matching = [
        event for event in events
        if getattr(
            getattr(event, "involved_object", None),
            "uid",
            None,
        ) == pod_uid
    ]

    def timestamp_key(event):
        timestamp = event_timestamp(event)

        if timestamp is None:
            return 0.0

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return timestamp.timestamp()

    return sorted(matching, key=timestamp_key)
