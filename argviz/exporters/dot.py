"""DOT format exporter for Graphviz."""

from __future__ import annotations

from typing import Any

from argviz.model import GraphModel
from argviz.styles import StyleRegistry, NodeStyle, EdgeStyle, truncate_label


def _escape_label(text: str, max_width: int = 25) -> str:
    """Escape and wrap label text for DOT format."""
    # Escape special characters
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\n", "\\n")

    # Wrap long lines
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        if current_length + len(word) + 1 > max_width and current_line:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
        else:
            current_line.append(word)
            current_length += len(word) + 1

    if current_line:
        lines.append(" ".join(current_line))

    return "\\n".join(lines)


def _quote_id(node_id: str) -> str:
    """Quote a node ID for DOT format.

    DOT requires quoting for IDs containing special characters
    (hyphens, spaces, dots, etc.) or starting with digits.
    We always quote for safety and consistency.
    """
    # Escape any quotes in the ID itself
    escaped = node_id.replace('"', '\\"')
    return f'"{escaped}"'


def _format_node_attrs(node_id: str, style: NodeStyle, label: str) -> str:
    """Format node attributes for DOT."""
    quoted_id = _quote_id(node_id)
    attrs = [
        f'label="{label}"',
        f'shape={style.shape}',
        'style=filled',
        f'fillcolor="{style.fill_color}"',
        f'color="{style.border_color}"',
    ]

    if style.fixed_size and style.width and style.height:
        attrs.extend([
            f'width={style.width}',
            f'height={style.height}',
            'fixedsize=true',
        ])

    return f'    {quoted_id} [{", ".join(attrs)}];'


def _format_edge(
    source: str,
    target: str,
    style: EdgeStyle,
    line_style_override: str | None = None,
) -> str:
    """Format an edge with styling for DOT.

    Args:
        source: Source node ID.
        target: Target node ID.
        style: Edge style to use.
        line_style_override: Optional override for line style (e.g., "dashed" for auxiliary edges).
    """
    quoted_source = _quote_id(source)
    quoted_target = _quote_id(target)

    line_style = line_style_override or style.line_style
    attrs = [
        f'color="{style.line_color}"',
        f'penwidth={style.line_width}',
    ]
    if line_style != "solid":
        attrs.append(f'style={line_style}')

    return f'    {quoted_source} -> {quoted_target} [{", ".join(attrs)}];'


class DOTExporter:
    """Export argument graphs to DOT format."""

    def __init__(self, styles: StyleRegistry | None = None) -> None:
        """Initialize exporter.

        Args:
            styles: Style registry for visual properties. Uses defaults if None.
        """
        self.styles = styles or StyleRegistry()

    def export(self, model: GraphModel) -> str:
        """Export graph to DOT format string.

        Args:
            model: The argument graph to export.

        Returns:
            DOT format string.
        """
        lines = [
            "digraph argument_graph {",
            "    // Graph settings",
            "    rankdir=BT;",
            "    splines=ortho;",
            "    nodesep=0.6;",
            "    ranksep=0.8;",
            "    bgcolor=white;",
            "",
            "    // Node defaults",
            '    node [fontname="Helvetica", fontsize=10];',
            '    edge [fontname="Helvetica", fontsize=9];',
            "",
        ]

        # Add content nodes (Propositions and Datums)
        lines.append("    // Content nodes")
        for node_id, node in model.nodes.items():
            style = self.styles.get_node_style(node)
            content = node.get("content", node_id)
            truncated_content, _ = truncate_label(content, self.styles.max_label_chars)
            label = _escape_label(truncated_content)
            lines.append(_format_node_attrs(node_id, style, label))
        lines.append("")

        # Add link nodes
        lines.append("    // Link nodes")
        for link_id, link in model.links.items():
            style = self.styles.get_node_style(link, is_link=True)
            lines.append(_format_node_attrs(link_id, style, ""))
        lines.append("")

        # Add edges from links
        lines.append("    // Link edges")
        for link_id, link in model.links.items():
            edge_style = self.styles.get_link_edge_style(link)

            # Edges from sources to link
            for source_id in link.get("source_ids", []):
                # Use dashed line for edges from auxiliary nodes
                source_node = model.nodes.get(source_id, {})
                is_auxiliary = source_node.get("auxiliary", False)
                line_style_override = "dashed" if is_auxiliary else None
                lines.append(_format_edge(source_id, link_id, edge_style, line_style_override))

            # Edge from link to target
            target_id = link.get("target_id")
            if target_id:
                lines.append(_format_edge(link_id, target_id, edge_style))
        lines.append("")

        lines.append("}")

        return "\n".join(lines)

    def export_to_file(self, model: GraphModel, filepath: str) -> None:
        """Export graph to a DOT file.

        Args:
            model: The argument graph to export.
            filepath: Output file path.
        """
        dot_content = self.export(model)
        with open(filepath, "w") as f:
            f.write(dot_content)
