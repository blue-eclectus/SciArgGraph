"""Argument graph visualization module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from argviz.parser import YAMLParser
from argviz.styles import StyleRegistry
from argviz.exporters.dot import DOTExporter
from argviz.exporters.svg import SVGExporter
from argviz.exporters.cytoscape import CytoscapeExporter

if TYPE_CHECKING:
    from argviz.model import GraphModel

__version__ = "0.1.0"

# Supported output formats
FORMATS = ["dot", "svg", "cytoscape-json", "cytoscape-html"]


def visualize(
    input_path: str | Path,
    output: str | Path | None = None,
    format: str = "dot",
    theme: str | None = None,
    max_label_chars: int = 100,
) -> str:
    """Visualize an argument graph.

    Args:
        input_path: Path to YAML argument graph file.
        output: Optional output file path. If None, returns content string.
        format: Output format - "dot", "svg", "cytoscape-json", or "cytoscape-html".
        theme: Optional path to theme YAML file.
        max_label_chars: Maximum label length before truncation (default 100).

    Returns:
        Visualization content as string (DOT, SVG, JSON, or HTML).

    Raises:
        ValueError: If format is not supported.
    """
    if format not in FORMATS:
        raise ValueError(
            f"Unsupported format: {format}. "
            f"Supported formats: {', '.join(FORMATS)}"
        )

    parser = YAMLParser()
    model = parser.parse(input_path)

    styles = StyleRegistry(theme=theme, max_label_chars=max_label_chars)

    if format == "dot":
        exporter = DOTExporter(styles)
        content = exporter.export(model)
    elif format == "svg":
        exporter = SVGExporter(styles)
        content = exporter.export(model)
    elif format == "cytoscape-json":
        exporter = CytoscapeExporter(styles)
        content = exporter.export(model, format="json")
    elif format == "cytoscape-html":
        exporter = CytoscapeExporter(styles)
        content = exporter.export(model, format="html")

    if output:
        Path(output).write_text(content)

    return content


def load(input_path: str | Path) -> "GraphModel":
    """Load an argument graph from YAML.

    Args:
        input_path: Path to YAML argument graph file.

    Returns:
        GraphModel instance.
    """
    parser = YAMLParser()
    return parser.parse(input_path)
