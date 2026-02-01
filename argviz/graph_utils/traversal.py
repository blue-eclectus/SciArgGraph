"""Path and tree operations for argument graphs."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    from argviz.model import GraphModel

# Type aliases
NodeId = str
PathList = list[NodeId]


def _build_support_graph(graph: GraphModel, support_only: bool = True) -> nx.DiGraph:
    """Build a NetworkX DiGraph of node-to-node relationships.

    This flattens the reified link structure into direct edges between nodes,
    optionally filtering to support relationships only.

    Args:
        graph: The argument graph.
        support_only: If True, only include support links.

    Returns:
        DiGraph with edges from source nodes to target nodes.
    """
    g = nx.DiGraph()

    # Add all nodes
    for node_id in graph.nodes:
        g.add_node(node_id)

    # Add edges from links
    for link in graph.links.values():
        if support_only and link.get("polarity") != "supports":
            continue

        target_id = link.get("target_id")
        if target_id and target_id in graph.nodes:
            for source_id in link.get("source_ids", []):
                if source_id in graph.nodes:
                    g.add_edge(source_id, target_id)

    return g


def get_ancestors(
    graph: GraphModel,
    node_id: NodeId,
    support_only: bool = True,
) -> list[NodeId]:
    """Get all nodes upstream of this node (transitive supporters).

    Follows support relationships backward to find all nodes
    that (directly or indirectly) support this node.

    Args:
        graph: The argument graph.
        node_id: Starting node.
        support_only: If True, only follow support links.
                      If False, include undermining relationships.

    Returns:
        List of all ancestor node IDs (excludes node_id itself).
    """
    if node_id not in graph.nodes:
        return []

    g = _build_support_graph(graph, support_only)
    return list(nx.ancestors(g, node_id))


def get_descendants(
    graph: GraphModel,
    node_id: NodeId,
    support_only: bool = True,
) -> list[NodeId]:
    """Get all nodes downstream of this node (transitively supported).

    Follows support relationships forward to find all nodes
    that this node (directly or indirectly) supports.

    Args:
        graph: The argument graph.
        node_id: Starting node.
        support_only: If True, only follow support links.
                      If False, include undermining relationships.

    Returns:
        List of all descendant node IDs (excludes node_id itself).
    """
    if node_id not in graph.nodes:
        return []

    g = _build_support_graph(graph, support_only)
    return list(nx.descendants(g, node_id))


def get_depth(graph: GraphModel, node_id: NodeId) -> int:
    """Get distance from nearest leaf.

    Leaves have depth 0. Nodes directly supported by leaves have depth 1, etc.

    Args:
        graph: The argument graph.
        node_id: Node to compute depth for.

    Returns:
        Distance to nearest leaf (0 for leaves themselves).
        Returns -1 if node not found.
    """
    if node_id not in graph.nodes:
        return -1

    g = _build_support_graph(graph, support_only=True)

    # BFS from node going backward (toward leaves)
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(node_id, 0)])

    while queue:
        current, dist = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        # Check if current is a leaf (no predecessors)
        preds = list(g.predecessors(current))
        if not preds:
            return dist

        for pred in preds:
            if pred not in visited:
                queue.append((pred, dist + 1))

    # Node is itself a leaf or disconnected
    return 0


def get_height(graph: GraphModel, node_id: NodeId) -> int:
    """Get distance to nearest root.

    Roots have height 0. Nodes that directly support roots have height 1, etc.

    Args:
        graph: The argument graph.
        node_id: Node to compute height for.

    Returns:
        Distance to nearest root (0 for roots themselves).
        Returns -1 if node not found.
    """
    if node_id not in graph.nodes:
        return -1

    g = _build_support_graph(graph, support_only=True)

    # BFS from node going forward (toward roots)
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(node_id, 0)])

    while queue:
        current, dist = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        # Check if current is a root (no successors)
        succs = list(g.successors(current))
        if not succs:
            return dist

        for succ in succs:
            if succ not in visited:
                queue.append((succ, dist + 1))

    # Node is itself a root or disconnected
    return 0


def get_paths(
    graph: GraphModel,
    source_id: NodeId,
    target_id: NodeId,
    support_only: bool = True,
) -> list[PathList]:
    """Get all reasoning paths from source to target.

    Returns all simple paths (no cycles) from source to target
    following support relationships.

    Args:
        graph: The argument graph.
        source_id: Starting node (typically a leaf/datum).
        target_id: Ending node (typically a root/conclusion).
        support_only: If True, only follow support links.

    Returns:
        List of paths, where each path is a list of node IDs.
        Empty list if no path exists.
    """
    if source_id not in graph.nodes or target_id not in graph.nodes:
        return []

    g = _build_support_graph(graph, support_only)

    try:
        return list(nx.all_simple_paths(g, source_id, target_id))
    except nx.NetworkXError:
        return []


def get_shortest_path(
    graph: GraphModel,
    source_id: NodeId,
    target_id: NodeId,
    support_only: bool = True,
) -> PathList | None:
    """Get the shortest reasoning path from source to target.

    Args:
        graph: The argument graph.
        source_id: Starting node.
        target_id: Ending node.
        support_only: If True, only follow support links.

    Returns:
        List of node IDs forming the shortest path, or None if no path exists.
    """
    if source_id not in graph.nodes or target_id not in graph.nodes:
        return None

    g = _build_support_graph(graph, support_only)

    try:
        return nx.shortest_path(g, source_id, target_id)
    except nx.NetworkXNoPath:
        return None


def get_subgraph(
    graph: GraphModel,
    node_ids: set[NodeId],
    include_links: bool = True,
) -> GraphModel:
    """Extract a subgraph containing specified nodes.

    Creates a new GraphModel containing only the specified nodes
    and (optionally) the links between them.

    Args:
        graph: The argument graph.
        node_ids: Nodes to include in the subgraph.
        include_links: Whether to include links between the nodes.

    Returns:
        New GraphModel containing the subgraph.
    """
    from argviz.model import GraphModel as GM

    # Filter nodes
    new_nodes = [
        node for node_id, node in graph.nodes.items()
        if node_id in node_ids
    ]

    # Filter links: include if all sources AND target are in node_ids
    new_links = []
    if include_links:
        for link in graph.links.values():
            source_ids = link.get("source_ids", [])
            target_id = link.get("target_id")

            if not all(sid in node_ids for sid in source_ids):
                continue
            if target_id and target_id not in node_ids:
                continue

            new_links.append(link)

    return GM({
        "nodes": new_nodes,
        "links": new_links,
    })


def topological_sort(graph: GraphModel) -> list[NodeId]:
    """Return nodes in topological order (leaves before dependents).

    Useful for bottom-up confidence propagation in Bayesian analysis.
    Leaves appear first, roots last.

    Returns:
        List of node IDs in topological order.

    Raises:
        ValueError: If graph contains cycles.
    """
    g = _build_support_graph(graph, support_only=True)

    try:
        return list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible as e:
        raise ValueError("Graph contains cycles") from e


def extract_support_subgraph(
    graph: GraphModel,
    node_id: NodeId,
) -> GraphModel:
    """Extract the complete support structure for a node.

    Returns a new GraphModel containing node_id, all its ancestors
    (transitive supporters), and all links between them.

    Args:
        graph: The argument graph.
        node_id: Root of the support subgraph.

    Returns:
        New GraphModel containing the support subgraph.
    """
    ancestors = get_ancestors(graph, node_id, support_only=True)
    nodes = set(ancestors) | {node_id}
    return get_subgraph(graph, nodes)


def extract_paths_subgraph(
    graph: GraphModel,
    source_id: NodeId,
    target_id: NodeId,
    support_only: bool = True,
) -> GraphModel:
    """Extract subgraph containing all paths between two nodes.

    Useful for understanding how a specific datum supports a specific
    conclusion through potentially multiple reasoning chains.

    Args:
        graph: The argument graph.
        source_id: Starting node (typically leaf/datum).
        target_id: Ending node (typically root/conclusion).
        support_only: If True, only follow support links.

    Returns:
        New GraphModel containing nodes/links on any path.
        Empty graph if no path exists.
    """
    from argviz.model import GraphModel as GM

    paths = get_paths(graph, source_id, target_id, support_only)

    if not paths:
        return GM({"nodes": [], "links": [], "edges": []})

    # Collect all nodes on any path
    nodes_on_paths: set[str] = set()
    for path in paths:
        nodes_on_paths.update(path)

    return get_subgraph(graph, nodes_on_paths)


def extract_connected_component(
    graph: GraphModel,
    node_id: NodeId,
) -> GraphModel:
    """Extract the connected component containing a node.

    Returns all nodes reachable from node_id following links
    in either direction, plus all links between them.

    Args:
        graph: The argument graph.
        node_id: Any node in the desired component.

    Returns:
        New GraphModel containing the connected component.
    """
    from argviz.model import GraphModel as GM

    if node_id not in graph.nodes:
        return GM({"nodes": [], "links": [], "edges": []})

    # Build undirected version for connectivity
    g = _build_support_graph(graph, support_only=False)
    undirected = g.to_undirected()

    # Get all nodes in the connected component
    component = nx.node_connected_component(undirected, node_id)

    return get_subgraph(graph, component)
