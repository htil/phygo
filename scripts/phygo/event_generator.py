"""Event file generation logic compatible with MNE Epochs."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EventRow:
    """Single event timing row: latency (samples), placeholder, label index."""

    latency: int
    placeholder: int
    label_index: int

    def to_line(self) -> str:
        return f"{self.latency}, {self.placeholder}, {self.label_index}"


def parse_labels(label_text: str) -> list[str]:
    labels = [label.strip() for label in label_text.split(",") if label.strip()]
    return labels


def validate_labels(labels: list[str]) -> tuple[bool, str]:
    if not labels:
        return False, "At least one event label is required."
    return True, ""


def validate_positive_int(value: str, field_name: str) -> tuple[int | None, str]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, f"{field_name} must be a whole number."
    if parsed <= 0:
        return None, f"{field_name} must be greater than zero."
    return parsed, ""


def validate_event_rows(rows: list[EventRow], labels: list[str]) -> tuple[bool, str]:
    if not rows:
        return False, "No events defined. Click Generate Event to create the event sequence."

    for index, row in enumerate(rows, start=1):
        if row.placeholder != 0:
            return False, f"Event {index}: placeholder column must be 0."
        if row.latency <= 0:
            return False, f"Event {index}: latency must be greater than zero."
        if row.label_index < 0 or row.label_index >= len(labels):
            return False, (
                f"Event {index}: label index {row.label_index} is out of range "
                f"(0-{len(labels) - 1})."
            )
    return True, ""


def generate_events(
    events_per_label: int,
    sfreq: int,
    epoch_length: int,
    labels: list[str],
) -> list[EventRow]:
    """Generate evenly spaced events cycling through labels in order."""
    epoch_size = sfreq * epoch_length
    total_events = events_per_label * len(labels)
    rows: list[EventRow] = []

    for i in range(total_events):
        latency = epoch_size * (i + 1)
        label_index = i % len(labels)
        rows.append(EventRow(latency=latency, placeholder=0, label_index=label_index))

    return rows


def estimate_duration_minutes(rows: list[EventRow], sfreq: int) -> float:
    if not rows:
        return 0.0
    last_latency_samples = rows[-1].latency
    duration_seconds = last_latency_samples / sfreq
    return round(duration_seconds / 60.0, 2)


def rows_to_event_text(rows: list[EventRow]) -> str:
    return "\n".join(row.to_line() for row in rows)


def labels_to_text(labels: list[str]) -> str:
    return ",".join(labels)


def save_event_files(
    base_name: str,
    rows: list[EventRow],
    labels: list[str],
    events_dir: str,
) -> tuple[str, str]:
    os.makedirs(events_dir, exist_ok=True)

    event_file_path = os.path.join(events_dir, f"{base_name}.txt")
    labels_file_path = os.path.join(events_dir, f"{base_name}_event_labels.txt")

    with open(event_file_path, "w", encoding="utf-8") as event_file:
        event_file.write(rows_to_event_text(rows))
        event_file.write("\n")

    with open(labels_file_path, "w", encoding="utf-8") as labels_file:
        labels_file.write(labels_to_text(labels))
        labels_file.write("\n")

    return event_file_path, labels_file_path
