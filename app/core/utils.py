"""Shared utilities for the ProtoRyde backend."""

import json
from typing import Any, Dict


def read_json(filepath: str) -> Dict[str, Any]:
    """Read and parse a JSON file."""
    with open(filepath, "r", encoding="utf-8") as fh:
        return json.load(fh)
