"""Event file generation logic compatible with MNE Epochs."""

from __future__ import annotations

import os
from dataclasses import dataclass

PRE_RECORD_PADDING_MS = 5000
REST_LABEL = "Rest"
DEFAULT_REST_MS = 3000


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


def labels_with_rest(stimulus_labels: list[str]) -> list[str]:
    if REST_LABEL in stimulus_labels:
        return stimulus_labels[:]
    return stimulus_labels + [REST_LABEL]


def rest_label_index(stimulus_labels: list[str]) -> int:
    return labels_with_rest(stimulus_labels).index(REST_LABEL)


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
        if row.latency < 0:
            return False, f"Event {index}: latency must be zero or greater."
        if row.label_index < 0 or row.label_index >= len(labels):
            return False, (
                f"Event {index}: label index {row.label_index} is out of range "
                f"(0-{len(labels) - 1})."
            )
    return True, ""


def ms_to_samples(time_ms: int, sfreq: int) -> int:
    return round((time_ms * sfreq) / 1000)


def interleaved_presentation_time_ms(row_index: int, latency_ms: int, rest_ms: int) -> int:
    """Timing for stimulus/rest rows: stim, rest, stim, rest, ..."""
    cycle_index = row_index // 2
    if row_index % 2 == 0:
        return PRE_RECORD_PADDING_MS + cycle_index * (latency_ms + rest_ms)
    return PRE_RECORD_PADDING_MS + cycle_index * (latency_ms + rest_ms) + latency_ms


def interleaved_presentation_time_samples(
    row_index: int, latency_ms: int, rest_ms: int, sfreq: int
) -> int:
    return ms_to_samples(interleaved_presentation_time_ms(row_index, latency_ms, rest_ms), sfreq)


def stimulus_count(events_per_label: int, stimulus_labels: list[str]) -> int:
    return events_per_label * len(stimulus_labels)


def generate_events(
    events_per_label: int,
    latency_ms: int,
    rest_ms: int,
    stimulus_labels: list[str],
    sfreq: int,
) -> list[EventRow]:
    """Generate stimulus events with Rest inserted between each stimulus."""
    total_stimuli = stimulus_count(events_per_label, stimulus_labels)
    rest_index = rest_label_index(stimulus_labels)
    rows: list[EventRow] = []
    row_index = 0

    for stimulus_index in range(total_stimuli):
        label_index = stimulus_index % len(stimulus_labels)
        rows.append(
            EventRow(
                latency=interleaved_presentation_time_samples(
                    row_index, latency_ms, rest_ms, sfreq
                ),
                placeholder=0,
                label_index=label_index,
            )
        )
        row_index += 1

        if stimulus_index < total_stimuli - 1:
            rows.append(
                EventRow(
                    latency=interleaved_presentation_time_samples(
                        row_index, latency_ms, rest_ms, sfreq
                    ),
                    placeholder=0,
                    label_index=rest_index,
                )
            )
            row_index += 1

    return rows


def estimate_duration_minutes(
    events_per_label: int,
    stimulus_label_count: int,
    latency_ms: int,
    rest_ms: int,
) -> float:
    total_stimuli = events_per_label * stimulus_label_count
    if total_stimuli <= 0:
        return 0.0

    rest_events = max(0, total_stimuli - 1)
    duration_seconds = (
        PRE_RECORD_PADDING_MS
        + (total_stimuli * latency_ms)
        + (rest_events * rest_ms)
    ) / 1000.0
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
