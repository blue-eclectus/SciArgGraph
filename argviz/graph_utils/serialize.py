"""Serialization utilities for graph_utils results."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from argviz.model import GraphModel


def graph_to_dict(graph: GraphModel) -> dict[str, Any]:
    """Convert GraphModel to JSON-serializable dict.

    Args:
        graph: The argument graph.

    Returns:
        Dict with 'nodes' and 'links' keys,
        suitable for JSON serialization.
    """
    return {
        "nodes": list(graph.nodes.values()),
        "links": list(graph.links.values()),
    }
