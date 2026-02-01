"""Graph model for argument graphs."""

from __future__ import annotations

from typing import Any

import networkx as nx


class InvalidReferenceError(ValueError):
    """Raised when a link references a non-existent node."""
    pass


class GraphModel:
    """Internal representation of an argument graph.

    Wraps a NetworkX DiGraph with domain-specific methods for
    traversing propositions, data, and links.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        """Build graph from parsed YAML data.

        Args:
            data: Dictionary with 'nodes' and 'links' keys.

        Raises:
            InvalidReferenceError: If a link references a non-existent node.
        """
        self._graph = nx.DiGraph()
        self._nodes: dict[str, dict[str, Any]] = {}
        self._links: dict[str, dict[str, Any]] = {}

        # Phase 1: Register all nodes (Propositions and Datums)
        for node in data.get("nodes", []):
            node_id = node["id"]
            self._nodes[node_id] = node
            self._graph.add_node(node_id, **node)

        # Phase 2: Register all links (so they can reference each other)
        for link in data.get("links", []):
            link_id = link["id"]
            self._links[link_id] = link
            self._graph.add_node(link_id, **link, _is_link=True)

        # Phase 3: Validate references and build edges
        for link_id, link in self._links.items():
            # Validate and add edges from sources to link
            for source_id in link.get("source_ids", []):
                self._validate_reference(source_id, link_id, "link source")
                self._graph.add_edge(source_id, link_id)

            # Validate and add edge from link to target
            target_id = link.get("target_id")
            if target_id:
                self._validate_reference(target_id, link_id, "link target")
                self._graph.add_edge(link_id, target_id)

    def _validate_reference(self, ref_id: str, context: str, ref_type: str) -> None:
        """Validate that a referenced node exists.

        A valid reference is either a node (Proposition/Datum) or a link.

        Raises:
            InvalidReferenceError: If reference doesn't exist.
        """
        if ref_id not in self._nodes and ref_id not in self._links:
            raise InvalidReferenceError(
                f"Invalid {ref_type} in {context}: '{ref_id}' does not exist"
            )

    @property
    def nodes(self) -> dict[str, dict[str, Any]]:
        """All proposition and datum nodes."""
        return self._nodes

    @property
    def links(self) -> dict[str, dict[str, Any]]:
        """All link nodes (reified relationships)."""
        return self._links

    def get_parents(self, node_id: str) -> list[str]:
        """Get IDs of nodes that have edges pointing to this node."""
        return list(self._graph.predecessors(node_id))

    def get_children(self, node_id: str) -> list[str]:
        """Get IDs of nodes that this node points to."""
        return list(self._graph.successors(node_id))

    def get_incoming_links(self, node_id: str) -> list[dict[str, Any]]:
        """Get Link nodes that target this node."""
        result = []
        for parent_id in self.get_parents(node_id):
            if parent_id in self._links:
                result.append(self._links[parent_id])
        return result

    def all_node_ids(self) -> list[str]:
        """Get all node IDs (propositions, datums, and links)."""
        return list(self._graph.nodes())

    @property
    def nx_graph(self) -> nx.DiGraph:
        """Access underlying NetworkX graph for advanced operations."""
        return self._graph

    def get_subgraph(
        self,
        root_ids: str | list[str],
        depth_up: int = 1,
        depth_down: int = 1,
    ) -> "GraphModel":
        """Extract a subgraph centered on the given node(s).

        Args:
            root_ids: Starting node ID(s) for extraction.
            depth_up: How many levels toward hypotheses (following edges forward).
            depth_down: How many levels toward evidence (following edges backward).

        Returns:
            New GraphModel containing only the extracted nodes and their connections.

        Raises:
            KeyError: If any root_id doesn't exist.
            ValueError: If depth_up or depth_down is negative.
        """
        # Validate depths are non-negative
        if depth_up < 0 or depth_down < 0:
            raise ValueError("depth_up and depth_down must be non-negative")

        # Normalize to list
        if isinstance(root_ids, str):
            root_ids = [root_ids]

        # Validate all roots exist
        all_ids = set(self._nodes.keys()) | set(self._links.keys())
        for root_id in root_ids:
            if root_id not in all_ids:
                raise KeyError(f"Node not found: {root_id}")

        # Collect nodes using BFS in both directions
        collected: set[str] = set()

        def bfs(start_ids: list[str], depth: int, get_neighbors) -> None:
            frontier = set(start_ids)
            for _ in range(depth + 1):
                collected.update(frontier)
                next_frontier: set[str] = set()
                for node_id in frontier:
                    next_frontier.update(get_neighbors(node_id))
                frontier = next_frontier - collected

        # Go up (toward hypotheses) - follow successors
        bfs(root_ids, depth_up, lambda n: self._graph.successors(n))

        # Go down (toward evidence) - follow predecessors
        bfs(root_ids, depth_down, lambda n: self._graph.predecessors(n))

        # Build new data structure with only collected nodes
        new_nodes = [
            node for node_id, node in self._nodes.items()
            if node_id in collected
        ]

        # Filter links: only include if all source_ids AND target_id are in collected
        new_links = []
        for link_id, link in self._links.items():
            if link_id not in collected:
                continue
            # Check all source_ids are in collected
            source_ids = link.get("source_ids", [])
            if not all(sid in collected for sid in source_ids):
                continue
            # Check target_id is in collected
            target_id = link.get("target_id")
            if target_id and target_id not in collected:
                continue
            new_links.append(link)

        return GraphModel({
            "nodes": new_nodes,
            "links": new_links,
        })
