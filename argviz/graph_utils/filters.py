"""Filtering operations for argument graphs."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from argviz.model import GraphModel

# Type aliases
NodeId = str
NodeDict = dict[str, Any]
LinkDict = dict[str, Any]
Polarity = Literal["supports", "undermines"]


def filter_by_type(
    graph: GraphModel,
    node_types: str | list[str],
) -> list[NodeId]:
    """Get all nodes matching the given type(s).

    Args:
        graph: The argument graph.
        node_types: Single type or list of types
                    (e.g., 'Proposition' or ['Proposition', 'Conclusion']).

    Returns:
        List of node IDs matching the type(s).
    """
    if isinstance(node_types, str):
        node_types = [node_types]

    type_set = set(node_types)
    return [
        node_id
        for node_id, node in graph.nodes.items()
        if node.get("type") in type_set
    ]


def filter_links_by_polarity(
    graph: GraphModel,
    polarity: Polarity,
) -> list[LinkDict]:
    """Get all links with a specific polarity.

    Args:
        graph: The argument graph.
        polarity: Either 'supports' or 'undermines'.

    Returns:
        List of Link dicts matching the polarity.
    """
    return [
        link
        for link in graph.links.values()
        if link.get("polarity") == polarity
    ]


def filter_by_base_rate(
    graph: GraphModel,
    min_rate: float | None = None,
    max_rate: float | None = None,
) -> list[NodeId]:
    """Get nodes within a base_rate range.

    Typically used for Datums which have base_rate reliability scores.
    Nodes without base_rate are excluded.

    Args:
        graph: The argument graph.
        min_rate: Minimum base_rate (inclusive). None for no minimum.
        max_rate: Maximum base_rate (inclusive). None for no maximum.

    Returns:
        List of node IDs with base_rate in the specified range.
    """
    result: list[NodeId] = []

    for node_id, node in graph.nodes.items():
        base_rate = node.get("base_rate")
        if base_rate is None:
            continue

        if min_rate is not None and base_rate < min_rate:
            continue
        if max_rate is not None and base_rate > max_rate:
            continue

        result.append(node_id)

    return result


def filter_nodes(
    graph: GraphModel,
    predicate: Callable[[NodeDict], bool],
) -> list[NodeId]:
    """Get nodes matching a custom predicate.

    Args:
        graph: The argument graph.
        predicate: Function taking node dict, returning bool.

    Returns:
        List of node IDs where predicate returns True.

    Examples:
        # Nodes with textual basis
        filter_nodes(graph, lambda n: n.get("textual_basis") is not None)

        # Nodes without textual basis
        filter_nodes(graph, lambda n: n.get("textual_basis") is None)

        # Leaf propositions
        leaves = set(get_leaves(graph))
        filter_nodes(graph, lambda n: n["id"] in leaves and n["type"] == "Proposition")
    """
    return [
        node_id
        for node_id, node in graph.nodes.items()
        if predicate(node)
    ]


def filter_links(
    graph: GraphModel,
    predicate: Callable[[LinkDict], bool],
) -> list[LinkDict]:
    """Get links matching a custom predicate.

    Args:
        graph: The argument graph.
        predicate: Function taking link dict, returning bool.

    Returns:
        List of Link dicts where predicate returns True.

    Examples:
        # Joint support links (multiple sources)
        filter_links(graph, lambda l: len(l.get("source_ids", [])) > 1)
    """
    return [
        link
        for link in graph.links.values()
        if predicate(link)
    ]
