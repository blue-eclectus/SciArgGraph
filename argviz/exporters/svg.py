"""SVG format exporter using Graphviz for layout."""

from __future__ import annotations

import json
import subprocess
from typing import Any

import svgwrite

from argviz.model import GraphModel
from argviz.styles import StyleRegistry, truncate_label


class SVGExporter:
    """Export argument graphs to SVG format.

    Uses Graphviz for layout computation, then renders to SVG
    using svgwrite for full styling control.
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
        # Generate DOT and get layout from Graphviz
        from argviz.exporters.dot import DOTExporter
        dot_exporter = DOTExporter(self.styles)
        dot_content = dot_exporter.export(model)

        # Get positions from Graphviz JSON output
        try:
            result = subprocess.run(
                ["dot", "-Tjson"],
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

        layout = json.loads(result.stdout)

        # Parse layout data
        bb = layout.get("bb", "0,0,100,100").split(",")
        width = float(bb[2])
        height = float(bb[3])

        # Create SVG drawing
        dwg = svgwrite.Drawing(size=(f"{width}pt", f"{height}pt"))
        dwg.viewbox(0, 0, width, height)

        # Add arrowhead marker definitions
        self._add_arrow_markers(dwg)

        # Add background (using theme color)
        bg_color = self.styles._get_color("background")
        dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill=bg_color))

        # Build node position lookup and index-to-name mapping
        node_positions: dict[str, dict[str, Any]] = {}
        index_to_name: dict[int, str] = {}
        for obj in layout.get("objects", []):
            if "_gvid" in obj and "name" in obj:
                index_to_name[obj["_gvid"]] = obj["name"]
            if "name" in obj and "pos" in obj:
                name = obj["name"]
                pos = obj["pos"].split(",")
                node_positions[name] = {
                    "x": float(pos[0]),
                    "y": height - float(pos[1]),  # Flip Y axis
                    "width": float(obj.get("width", 1)) * 72,  # inches to points
                    "height": float(obj.get("height", 0.5)) * 72,
                }

        # Draw edges first (behind nodes)
        for edge in layout.get("edges", []):
            self._draw_edge(dwg, edge, height, model, index_to_name)

        # Draw nodes
        for node_id, node in model.nodes.items():
            if node_id in node_positions:
                pos = node_positions[node_id]
                self._draw_content_node(dwg, node_id, node, pos)

        for link_id, link in model.links.items():
            if link_id in node_positions:
                pos = node_positions[link_id]
                self._draw_link_node(dwg, link_id, link, pos)

        return dwg.tostring()

    def _draw_content_node(
        self,
        dwg: svgwrite.Drawing,
        node_id: str,
        node: dict[str, Any],
        pos: dict[str, float],
    ) -> None:
        """Draw a content node (Proposition or Datum)."""
        style = self.styles.get_node_style(node)
        content = node.get("content", node_id)
        label, was_truncated = truncate_label(content, self.styles.max_label_chars)

        x, y = pos["x"], pos["y"]
        w, h = pos["width"], pos["height"]

        # Create group for node
        g = dwg.g()

        if style.shape == "ellipse":
            shape = dwg.ellipse(
                center=(x, y),
                r=(w / 2, h / 2),
                fill=style.fill_color,
                stroke=style.border_color,
                stroke_width=style.border_width,
            )
        else:  # box
            shape = dwg.rect(
                insert=(x - w / 2, y - h / 2),
                size=(w, h),
                fill=style.fill_color,
                stroke=style.border_color,
                stroke_width=style.border_width,
                rx=3,
                ry=3,
            )

        g.add(shape)

        # Add label text
        text = dwg.text(
            label.replace("\\n", "\n"),
            insert=(x, y),
            text_anchor="middle",
            dominant_baseline="middle",
            font_family=style.font_family,
            font_size=style.font_size,
        )
        g.add(text)

        dwg.add(g)

    def _draw_link_node(
        self,
        dwg: svgwrite.Drawing,
        link_id: str,
        link: dict[str, Any],
        pos: dict[str, float],
    ) -> None:
        """Draw a link node (diamond)."""
        style = self.styles.get_node_style(link, is_link=True)

        x, y = pos["x"], pos["y"]
        size = 10  # Small diamond

        # Diamond points
        points = [
            (x, y - size),      # top
            (x + size, y),      # right
            (x, y + size),      # bottom
            (x - size, y),      # left
        ]

        g = dwg.g()

        diamond = dwg.polygon(
            points=points,
            fill=style.fill_color,
            stroke=style.border_color,
            stroke_width=style.border_width,
        )
        g.add(diamond)
        dwg.add(g)

    def _add_arrow_markers(self, dwg: svgwrite.Drawing) -> None:
        """Add arrowhead marker definitions to the SVG."""
        # Create markers for different edge colors
        colors = [
            ("arrow_supports", self.styles._get_color("edge_supports")),
            ("arrow_undermines", self.styles._get_color("edge_undermines")),
            ("arrow_default", self.styles._get_color("edge_default")),
        ]

        for marker_id, color in colors:
            marker = dwg.marker(
                id=marker_id,
                insert=(8, 4),
                size=(10, 8),
                orient="auto",
                markerUnits="strokeWidth",
            )
            marker.add(dwg.path(
                d="M 0 0 L 10 4 L 0 8 z",
                fill=color,
            ))
            dwg.defs.add(marker)

    def _get_arrow_marker_id(self, style) -> str:
        """Get the appropriate arrow marker ID for an edge style."""
        color = style.line_color.upper()
        supports = self.styles._get_color("edge_supports").upper()
        undermines = self.styles._get_color("edge_undermines").upper()

        if color == supports:
            return "arrow_supports"
        elif color == undermines:
            return "arrow_undermines"
        return "arrow_default"

    def _draw_edge(
        self,
        dwg: svgwrite.Drawing,
        edge_data: dict[str, Any],
        height: float,
        model: GraphModel,
        index_to_name: dict[int, str],
    ) -> None:
        """Draw an edge."""
        # Get edge style based on type
        # Graphviz JSON uses numeric indices for tail/head, translate to node names
        tail_idx = edge_data.get("tail")
        head_idx = edge_data.get("head")
        tail = index_to_name.get(tail_idx, str(tail_idx))
        head = index_to_name.get(head_idx, str(head_idx))

        # Check if this is an edge from an auxiliary node to a link
        is_auxiliary_edge = False
        if tail in model.nodes and head in model.links:
            source_node = model.nodes.get(tail, {})
            is_auxiliary_edge = source_node.get("auxiliary", False)

        # Determine edge type for styling
        if tail in model.links:
            link = model.links[tail]
            style = self.styles.get_link_edge_style(link)
        elif head in model.links:
            link = model.links[head]
            style = self.styles.get_link_edge_style(link)
        else:
            # Default edge style
            style = EdgeStyle(
                line_color=self.styles._get_color("edge_default"),
                line_style="solid",
            )

        # Use dashed line for edges from auxiliary nodes
        line_style = "dashed" if is_auxiliary_edge else style.line_style

        # Parse spline points
        if "_draw_" in edge_data:
            for draw_op in edge_data["_draw_"]:
                if draw_op.get("op") == "b":  # bezier
                    points = draw_op.get("points", [])
                    if points:
                        path_data = f"M {points[0][0]},{height - points[0][1]}"
                        for i in range(1, len(points), 3):
                            if i + 2 < len(points):
                                path_data += f" C {points[i][0]},{height - points[i][1]}"
                                path_data += f" {points[i+1][0]},{height - points[i+1][1]}"
                                path_data += f" {points[i+2][0]},{height - points[i+2][1]}"

                        marker_id = self._get_arrow_marker_id(style)
                        path_kwargs = {
                            "d": path_data,
                            "stroke": style.line_color,
                            "stroke_width": style.line_width,
                            "fill": "none",
                        }
                        if line_style == "dashed":
                            path_kwargs["stroke_dasharray"] = "5,3"

                        path = dwg.path(**path_kwargs)
                        path["marker-end"] = f"url(#{marker_id})"
                        dwg.add(path)
