"""Shared configuration and project paths."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT_DIR / "data" / "instances"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "outputs"
