"""Physiological data recording and file persistence helpers."""

from __future__ import annotations

import os

import pandas as pd


def ensure_directory(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def resolve_storage_paths(project_dir: str) -> tuple[str, str, str]:
    """Resolve project root plus flat events/ and data/ directories."""
    root = os.path.abspath(project_dir.strip())
    base_name = os.path.basename(root.rstrip(os.sep))

    if base_name in ("data", "events"):
        root = os.path.dirname(root)

    events_dir = os.path.join(root, "events")
    data_dir = os.path.join(root, "data")
    return root, events_dir, data_dir


def recording_filename(base_name: str) -> str:
    base = base_name.strip()
    if base.endswith("_data"):
        return f"{base}.csv"
    return f"{base}_data.csv"


def validate_output_directory(path: str) -> tuple[bool, str]:
    if not path or not path.strip():
        return False, "Save location is required."

    normalized = os.path.abspath(path.strip())
    target_dir = normalized
    if not os.path.exists(target_dir):
        target_dir = os.path.dirname(normalized) or normalized

    if os.path.exists(target_dir):
        if not os.path.isdir(target_dir):
            return False, f"Save location is not a directory: {target_dir}"
        if not os.access(target_dir, os.W_OK):
            return False, f"Cannot write to directory: {target_dir}"
        return True, ""

    parent = os.path.dirname(target_dir)
    if parent and os.path.exists(parent) and not os.access(parent, os.W_OK):
        return False, f"Cannot create directory under: {parent}"

    return True, ""


def save_recording_dataframe(df: pd.DataFrame, data_dir: str, base_name: str) -> str:
    ensure_directory(data_dir)
    output_path = os.path.join(data_dir, recording_filename(base_name))
    df.to_csv(output_path, index=False)
    return output_path
