"""SVG format exporter using Graphviz."""

from __future__ import annotations

import subprocess

from argviz.model import GraphModel
from argviz.styles import StyleRegistry


class SVGExporter:
    """Export argument graphs to SVG format.

    Uses Graphviz to generate DOT and render directly to SVG.
    """

    def __init__(self, styles: StyleRegistry | None = None) -> None:
        """Initialize exporter.

        Args:
            styles: Style registry for visual properties. Uses defaults if None.
        """
        self.styles = styles or StyleRegistry()

    def export(self, model: GraphModel) -> str:
        """Export graph to SVG format string.

        Args:
            model: The argument graph to export.

        Returns:
            SVG format string.

        Raises:
            RuntimeError: If Graphviz is not installed.
        """
        # Generate DOT
        from argviz.exporters.dot import DOTExporter
        dot_exporter = DOTExporter(self.styles)
        dot_content = dot_exporter.export(model)

        # Use Graphviz to render SVG directly
        try:
            result = subprocess.run(
                ["dot", "-Tsvg"],
                input=dot_content,
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Graphviz not found. Install with: brew install graphviz"
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Graphviz error: {e.stderr}")

        return result.stdout
