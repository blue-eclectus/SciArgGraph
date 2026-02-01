"""Computed properties for argument graphs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx

from .traversal import _build_support_graph, get_ancestors

if TYPE_CHECKING:
    from argviz.model import GraphModel

# Type aliases
NodeId = str
LinkDict = dict[str, Any]


def compute_graph_stats(graph: GraphModel) -> dict[str, Any]:
    """Compute summary statistics for the graph.

    Returns:
        Dict with keys:
        - node_count: Total number of nodes
        - link_count: Total number of links
        - nodes_by_type: Dict mapping NodeType to count
        - links_by_polarity: Dict mapping Polarity to count
        - max_depth: Longest path from leaf to root
        - avg_supporters: Average number of supporters per non-leaf node
    """
    # Count nodes by type
    nodes_by_type: dict[str, int] = {}
    for node in graph.nodes.values():
        node_type = node.get("type", "Unknown")
        nodes_by_type[node_type] = nodes_by_type.get(node_type, 0) + 1

    # Count links by polarity
    links_by_polarity: dict[str, int] = {}
    for link in graph.links.values():
        polarity = link.get("polarity", "unknown")
        links_by_polarity[polarity] = links_by_polarity.get(polarity, 0) + 1

    # Compute max depth (longest path)
    g = _build_support_graph(graph, support_only=True)
    try:
        max_depth = nx.dag_longest_path_length(g) if g.number_of_edges() > 0 else 0
    except nx.NetworkXUnfeasible:
        # Graph has cycles
        max_depth = -1

    # Compute average supporters per non-leaf node
    supporter_counts = []
    for node_id in graph.nodes:
        supporters = list(g.predecessors(node_id))
        if supporters:  # Non-leaf node
            supporter_counts.append(len(supporters))

    avg_supporters = (
        sum(supporter_counts) / len(supporter_counts)
        if supporter_counts
        else 0.0
    )

    return {
        "node_count": len(graph.nodes),
        "link_count": len(graph.links),
        "nodes_by_type": nodes_by_type,
        "links_by_polarity": links_by_polarity,
        "max_depth": max_depth,
        "avg_supporters": round(avg_supporters, 2),
    }


def find_ungrounded_claims(graph: GraphModel) -> list[NodeId]:
    """Find Propositions with no Datum ancestry.

    These are claims that aren't ultimately grounded in any
    empirical evidence - purely assumptive.

    Returns:
        List of Proposition node IDs with no Datum ancestors.
    """
    result: list[NodeId] = []

    # Get all datum IDs
    datum_ids = {
        node_id
        for node_id, node in graph.nodes.items()
        if node.get("type") == "Datum"
    }

    # Check each proposition
    for node_id, node in graph.nodes.items():
        if node.get("type") != "Proposition":
            continue

        ancestors = set(get_ancestors(graph, node_id, support_only=True))
        # Check if any ancestor is a datum
        if not ancestors & datum_ids:
            result.append(node_id)

    return result


def find_weakly_supported(
    graph: GraphModel,
    min_supporters: int = 2,
) -> list[NodeId]:
    """Find nodes with fewer than min_supporters direct supporters.

    Args:
        graph: The argument graph.
        min_supporters: Minimum number of supporters to be "well-supported".

    Returns:
        List of node IDs with insufficient support.
    """
    g = _build_support_graph(graph, support_only=True)

    result: list[NodeId] = []
    for node_id in graph.nodes:
        supporter_count = g.in_degree(node_id)
        if 0 < supporter_count < min_supporters:
            result.append(node_id)

    return result


def check_acyclic(graph: GraphModel) -> bool:
    """Verify the graph has no cycles.

    Valid argument graphs should be DAGs. This detects circular reasoning.

    Returns:
        True if graph is acyclic, False if cycles exist.
    """
    g = _build_support_graph(graph, support_only=False)
    return nx.is_directed_acyclic_graph(g)


def find_cycles(graph: GraphModel) -> list[list[NodeId]]:
    """Find all cycles in the graph (circular reasoning).

    Returns:
        List of cycles, where each cycle is a list of node IDs.
        Empty list if graph is acyclic.
    """
    g = _build_support_graph(graph, support_only=False)

    try:
        cycles = list(nx.simple_cycles(g))
        return cycles
    except nx.NetworkXError:
        return []


def find_isolated_nodes(graph: GraphModel) -> list[NodeId]:
    """Find nodes with no incoming or outgoing links.

    These shouldn't exist in valid argument graphs - indicates
    extraction issues or orphaned claims.

    Returns:
        List of node IDs with no connections.
    """
    g = _build_support_graph(graph, support_only=False)

    return [
        node_id
        for node_id in graph.nodes
        if g.in_degree(node_id) == 0 and g.out_degree(node_id) == 0
    ]


def get_links_targeting_links(graph: GraphModel) -> list[LinkDict]:
    """Find links that target other links (undercutting defeaters).

    These attack the inferential connection rather than the premise.
    In the graph model, link targets can be other link IDs.

    Returns:
        List of link dicts where target_id is another link.
    """
    link_ids = set(graph.links.keys())

    return [
        link
        for link in graph.links.values()
        if link.get("target_id") in link_ids
    ]
