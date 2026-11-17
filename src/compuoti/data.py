"""Load and validate CompuOpti instance files.

IMPORTANT: implement the mapping only after inspecting the exact course JSON schema.
Keep JSON-specific key names inside this module; the optimization model should consume
a normalized Instance object rather than depend on raw JSON keys.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class Instance:
    """Normalized optimization input.

    Replace the placeholder fields with typed sets/parameters after confirming the
    supplied JSON schema and professor's specification.
    """
    raw: dict[str, Any]
    source: Path


def load_instance(path: str | Path) -> Instance:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Instance file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)
    if not isinstance(raw, dict):
        raise ValueError("Expected the instance JSON root to be an object.")
    return Instance(raw=raw, source=path)


def validate_instance(instance: Instance) -> list[str]:
    """Return validation errors. Extend this after documenting the JSON schema."""
    errors: list[str] = []
    if not instance.raw:
        errors.append("The instance JSON object is empty.")
    # TODO: validate employee, project, qualification, horizon, leave,
    # requirements, gains, penalties, and deadlines against the real schema.
    return errors
