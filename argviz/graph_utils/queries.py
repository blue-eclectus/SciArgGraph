"""Structural queries for argument graphs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from argviz.model import GraphModel

# Type aliases
NodeId = str
NodeDict = dict[str, Any]
LinkDict = dict[str, Any]
Polarity = Literal["supports", "undermines"]
Direction = Literal["incoming", "outgoing"]


def get_node(graph: GraphModel, node_id: NodeId) -> NodeDict | None:
    """Get a node by ID.

    Args:
        graph: The argument graph.
        node_id: ID of the node to retrieve.

    Returns:
        Node dict if found, None otherwise.
    """
    return graph.nodes.get(node_id)


def get_link(graph: GraphModel, link_id: str) -> LinkDict | None:
    """Get a link by ID.

    Args:
        graph: The argument graph.
        link_id: ID of the link to retrieve.

    Returns:
        Link dict if found, None otherwise.
    """
    return graph.links.get(link_id)


def get_all_nodes(graph: GraphModel) -> list[NodeDict]:
    """Get all nodes in the graph.

    Returns:
        List of all node dicts (Propositions, Datums, Conclusions).
    """
    return list(graph.nodes.values())


def get_all_links(graph: GraphModel) -> list[LinkDict]:
    """Get all links in the graph.

    Returns:
        List of all link dicts.
    """
    return list(graph.links.values())


def has_node(graph: GraphModel, node_id: NodeId) -> bool:
    """Check if a node exists in the graph.

    Args:
        graph: The argument graph.
        node_id: ID to check.

    Returns:
        True if node exists, False otherwise.
    """
    return node_id in graph.nodes


def get_roots(graph: GraphModel) -> list[NodeId]:
    """Get root nodes (conclusions with no outgoing support).

    A root is a node that does not act as a source for any support link.
    These are typically the main claims being argued for - endpoints of
    argumentative chains.

    Returns:
        List of node IDs that are argumentative roots.
    """
    # Collect all nodes that are sources in any link
    sources: set[str] = set()
    for link in graph.links.values():
        sources.update(link.get("source_ids", []))

    # Roots are nodes that are not sources
    return [node_id for node_id in graph.nodes if node_id not in sources]


def get_leaves(graph: GraphModel) -> list[NodeId]:
    """Get leaf nodes (nodes with no incoming support).

    A leaf is a node that receives no support from other nodes.
    These are foundational assumptions - datums or ungrounded propositions.

    Returns:
        List of node IDs that are argumentative leaves.
    """
    # Collect all nodes that are targets of support links
    targets: set[str] = set()
    for link in graph.links.values():
        if link.get("polarity") == "supports":
            target_id = link.get("target_id")
            if target_id and target_id in graph.nodes:
                targets.add(target_id)

    # Leaves are nodes that are not targets of any support
    return [node_id for node_id in graph.nodes if node_id not in targets]


def get_related_nodes(
    graph: GraphModel,
    node_id: NodeId,
    direction: Direction,
    polarity: Polarity | None = None,
) -> list[NodeId]:
    """Get nodes related to this node via links.

    Args:
        graph: The argument graph.
        node_id: Reference node.
        direction: "incoming" for nodes that target this node,
                   "outgoing" for nodes this node targets.
        polarity: Filter by link polarity. None for all polarities.

    Returns:
        List of related node IDs.

    Examples:
        # Get supporters (nodes that support this node)
        get_related_nodes(graph, "P1", "incoming", "supports")

        # Get attackers (nodes that undermine this node)
        get_related_nodes(graph, "P1", "incoming", "undermines")

        # Get nodes this node supports
        get_related_nodes(graph, "P1", "outgoing", "supports")
    """
    result: list[NodeId] = []

    for link in graph.links.values():
        # Filter by polarity if specified
        if polarity is not None and link.get("polarity") != polarity:
            continue

        if direction == "incoming":
            # Links targeting this node -> return their sources
            if link.get("target_id") == node_id:
                for source_id in link.get("source_ids", []):
                    if source_id in graph.nodes and source_id not in result:
                        result.append(source_id)
        else:  # outgoing
            # Links where this node is a source -> return their targets
            if node_id in link.get("source_ids", []):
                target_id = link.get("target_id")
                if target_id and target_id in graph.nodes and target_id not in result:
                    result.append(target_id)

    return result


def get_links_for_node(
    graph: GraphModel,
    node_id: NodeId,
    direction: Direction,
    polarity: Polarity | None = None,
) -> list[LinkDict]:
    """Get links connected to this node.

    Args:
        graph: The argument graph.
        node_id: Reference node.
        direction: "incoming" for links targeting this node,
                   "outgoing" for links where this node is a source.
        polarity: Filter by link polarity. None for all polarities.

    Returns:
        List of link dicts.

    Examples:
        # Get supporting links targeting this node
        get_links_for_node(graph, "P1", "incoming", "supports")

        # Get all outgoing links from this node
        get_links_for_node(graph, "P1", "outgoing", None)
    """
    result: list[LinkDict] = []

    for link in graph.links.values():
        # Filter by polarity if specified
        if polarity is not None and link.get("polarity") != polarity:
            continue

        if direction == "incoming":
            # Links targeting this node
            if link.get("target_id") == node_id:
                result.append(link)
        else:  # outgoing
            # Links where this node is a source
            if node_id in link.get("source_ids", []):
                result.append(link)

    return result
