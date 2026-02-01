"""YAML parser for argument graphs."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from argviz.model import GraphModel


def _load_bundled_schema() -> dict[str, Any]:
    """Load the bundled JSON schema from package resources."""
    try:
        # Python 3.11+ style
        schema_file = resources.files("argviz.schema").joinpath("argument_graph_schema.json")
        return json.loads(schema_file.read_text())
    except (FileNotFoundError, TypeError):
        # Fallback if schema not bundled (development mode)
        return {}


class SchemaValidationError(ValueError):
    """Raised when input data fails schema validation."""
    pass


class YAMLParser:
    """Load and validate argument graph YAML files.

    Handles schema-compliant YAML where all node types (Proposition, Conclusion,
    Datum, Link) are in a single 'nodes' array, discriminated by the 'type' field.
    """

    def __init__(self, schema_path: str | Path | None = None) -> None:
        """Initialize parser with optional custom schema.

        Args:
            schema_path: Path to JSON schema. Uses bundled schema if None.
        """
        if schema_path:
            with open(schema_path) as f:
                self._schema = json.load(f)
        else:
            self._schema = _load_bundled_schema() or self._minimal_schema()

    def _minimal_schema(self) -> dict[str, Any]:
        """Return minimal schema for essential validation.

        Used as fallback when bundled schema is not available.
        Matches the official schema structure where Links are in 'nodes' array.
        """
        return {
            "type": "object",
            "required": ["nodes"],
            "properties": {
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["type", "id"],
                        "properties": {
                            "id": {"type": "string"},
                            "type": {"type": "string", "enum": ["Proposition", "Conclusion", "Datum", "Link"]},
                            "content": {"type": "string"},
                            "source": {"type": "string"},
                            "source_ids": {"type": "array", "items": {"type": "string"}},
                            "target_id": {"type": "string"},
                            "polarity": {"type": "string", "enum": ["supports", "undermines"]},
                        },
                    },
                },
                "edges": {"type": "array"},
            },
        }

    def parse(self, filepath: str | Path) -> GraphModel:
        """Parse a YAML file and return a GraphModel.

        The YAML file should follow the schema format where all node types
        (Proposition, Datum, Link) are in a single 'nodes' array. This method
        separates them for internal processing.

        Args:
            filepath: Path to the YAML file.

        Returns:
            GraphModel instance.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If YAML is malformed.
            SchemaValidationError: If data fails schema validation.
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            with open(filepath) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}") from e

        if data is None:
            data = {}

        # Validate against schema
        self._validate(data)

        # Separate nodes by type: Links go to 'links', others to 'nodes'
        all_nodes = data.get("nodes", [])
        content_nodes = []
        links = []

        for node in all_nodes:
            if node.get("type") == "Link":
                links.append(node)
            else:
                content_nodes.append(node)

        # Build normalized structure for GraphModel
        normalized = {
            "metadata": data.get("metadata", {}),
            "nodes": content_nodes,
            "links": links,
            "edges": data.get("edges", []),
        }

        return GraphModel(normalized)

    def _validate(self, data: dict[str, Any]) -> None:
        """Validate data against schema.

        Raises:
            SchemaValidationError: If validation fails.
        """
        try:
            jsonschema.validate(data, self._schema)
        except jsonschema.ValidationError as e:
            # Extract the most relevant part of the error message
            field = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            raise SchemaValidationError(
                f"Schema validation failed at '{field}': {e.message}"
            ) from e
