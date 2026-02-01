"""Cytoscape format exporter (JSON and HTML)."""

from __future__ import annotations

import json
from typing import Any

from argviz.model import GraphModel
from argviz.styles import StyleRegistry, truncate_label


class CytoscapeExporter:
    """Export argument graphs to Cytoscape formats.

    Supports two output formats:
    - JSON: For embedding in web applications
    - HTML: Self-contained interactive viewer
    """

    def __init__(self, styles: StyleRegistry | None = None) -> None:
        """Initialize exporter.

        Args:
            styles: Style registry for visual properties. Uses defaults if None.
        """
        self.styles = styles or StyleRegistry()

    def export(self, model: GraphModel, format: str = "json") -> str:
        """Export graph to Cytoscape format.

        Args:
            model: The argument graph to export.
            format: Output format - "json" or "html".

        Returns:
            JSON string or HTML string.
        """
        if format == "json":
            return self._export_json(model)
        elif format == "html":
            return self._export_html(model)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_json(self, model: GraphModel) -> str:
        """Export to Cytoscape JSON format."""
        data = self._build_cytoscape_data(model)
        return json.dumps(data, indent=2)

    def _export_html(self, model: GraphModel) -> str:
        """Export to self-contained HTML with Cytoscape.js."""
        data = self._build_cytoscape_data(model)
        json_data = json.dumps(data, indent=2)

        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Argument Graph</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Helvetica, Arial, sans-serif;
        }}
        #cy {{
            width: 100%;
            height: 100vh;
        }}
        #tooltip {{
            position: absolute;
            display: none;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 10px;
            border-radius: 5px;
            max-width: 300px;
            font-size: 12px;
            z-index: 1000;
        }}
    </style>
</head>
<body>
    <div id="cy"></div>
    <div id="tooltip"></div>
    <script>
        const graphData = {json_data};

        const cy = cytoscape({{
            container: document.getElementById('cy'),
            elements: graphData.elements,
            style: graphData.style,
            layout: graphData.layout,
            userZoomingEnabled: true,
            userPanningEnabled: true,
            boxSelectionEnabled: false,
        }});

        // Tooltip on hover/click
        const tooltip = document.getElementById('tooltip');

        cy.on('tap', 'node', function(evt) {{
            const node = evt.target;
            const fullText = node.data('fullText');
            if (fullText) {{
                tooltip.innerHTML = fullText;
                tooltip.style.display = 'block';
                tooltip.style.left = evt.originalEvent.pageX + 10 + 'px';
                tooltip.style.top = evt.originalEvent.pageY + 10 + 'px';
            }}
        }});

        cy.on('tap', function(evt) {{
            if (evt.target === cy) {{
                tooltip.style.display = 'none';
            }}
        }});
    </script>
</body>
</html>'''
        return html

    def _build_cytoscape_data(self, model: GraphModel) -> dict[str, Any]:
        """Build Cytoscape data structure."""
        nodes = []
        edges = []

        # Add content nodes
        for node_id, node in model.nodes.items():
            style = self.styles.get_node_style(node)
            content = node.get("content", node_id)
            label, _ = truncate_label(content, self.styles.max_label_chars)

            nodes.append({
                "data": {
                    "id": node_id,
                    "label": label,
                    "fullText": content,
                    "type": node.get("type", "Proposition"),
                    "nodeColor": style.fill_color,
                    "borderColor": style.border_color,
                }
            })

        # Add link nodes
        for link_id, link in model.links.items():
            style = self.styles.get_node_style(link, is_link=True)
            polarity = link.get("polarity", "supports")

            nodes.append({
                "data": {
                    "id": link_id,
                    "label": "",
                    "fullText": f"Link ({polarity})",
                    "type": "Link",
                    "polarity": polarity,
                    "nodeColor": style.fill_color,
                    "borderColor": style.border_color,
                }
            })

            # Add edges from sources to link
            edge_style = self.styles.get_link_edge_style(link)
            for source_id in link.get("source_ids", []):
                # Use dashed line for edges from auxiliary nodes
                source_node = model.nodes.get(source_id, {})
                is_auxiliary = source_node.get("auxiliary", False)
                line_style = "dashed" if is_auxiliary else edge_style.line_style

                edges.append({
                    "data": {
                        "source": source_id,
                        "target": link_id,
                        "edgeType": "link",
                        "edgeColor": edge_style.line_color,
                        "lineStyle": line_style,
                    }
                })

            # Add edge from link to target
            target_id = link.get("target_id")
            if target_id:
                edges.append({
                    "data": {
                        "source": link_id,
                        "target": target_id,
                        "edgeType": "link",
                        "edgeColor": edge_style.line_color,
                        "lineStyle": edge_style.line_style,
                    }
                })

        # Build style array
        style = self._build_style()

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            },
            "style": style,
            "layout": {
                "name": "dagre",
                "rankDir": "BT",
                "nodeSep": 50,
                "rankSep": 80,
            },
        }

    def _build_style(self) -> list[dict[str, Any]]:
        """Build Cytoscape style array."""
        return [
            # Node styles
            {
                "selector": "node[type='Proposition']",
                "style": {
                    "shape": "round-rectangle",
                    "background-color": "data(nodeColor)",
                    "border-color": "data(borderColor)",
                    "border-width": 1,
                    "label": "data(label)",
                    "text-wrap": "wrap",
                    "text-max-width": "150px",
                    "font-size": "10px",
                    "text-valign": "center",
                    "text-halign": "center",
                    "width": "label",
                    "height": "label",
                    "padding": "10px",
                },
            },
            {
                "selector": "node[type='Conclusion']",
                "style": {
                    "shape": "round-rectangle",
                    "background-color": "data(nodeColor)",
                    "border-color": "data(borderColor)",
                    "border-width": 2,  # Thicker border to emphasize terminal claim
                    "label": "data(label)",
                    "text-wrap": "wrap",
                    "text-max-width": "150px",
                    "font-size": "10px",
                    "text-valign": "center",
                    "text-halign": "center",
                    "width": "label",
                    "height": "label",
                    "padding": "10px",
                },
            },
            {
                "selector": "node[type='Datum']",
                "style": {
                    "shape": "ellipse",
                    "background-color": "data(nodeColor)",
                    "border-color": "data(borderColor)",
                    "border-width": 1,
                    "label": "data(label)",
                    "text-wrap": "wrap",
                    "text-max-width": "150px",
                    "font-size": "10px",
                    "text-valign": "center",
                    "text-halign": "center",
                    "width": "label",
                    "height": "label",
                    "padding": "10px",
                },
            },
            {
                "selector": "node[type='Link']",
                "style": {
                    "shape": "diamond",
                    "background-color": "data(nodeColor)",
                    "border-color": "data(borderColor)",
                    "border-width": 1,
                    "width": 20,
                    "height": 20,
                },
            },
            # Edge styles
            {
                "selector": "edge",
                "style": {
                    "width": 1.5,
                    "line-color": "data(edgeColor)",
                    "target-arrow-color": "data(edgeColor)",
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier",
                },
            },
            {
                "selector": "edge[lineStyle='dashed']",
                "style": {
                    "line-style": "dashed",
                },
            },
        ]
