"""Graph utilities for querying and analyzing argument graphs.

This module provides reusable primitives for structural queries, filtering,
traversal, and analysis of GraphModel instances.

Example usage:
    from argviz.graph_utils import (
        get_leaves,
        get_ancestors,
        filter_by_type,
        compute_graph_stats,
    )

    # Find all leaf nodes
    leaves = get_leaves(graph)

    # Get support ancestry for a node
    ancestors = get_ancestors(graph, "P1")

    # Filter by node type
    conclusions = filter_by_type(graph, "Conclusion")

    # Get graph statistics
    stats = compute_graph_stats(graph)
"""

# Queries - structural lookups
from .queries import (
    get_node,
    get_link,
    get_all_nodes,
    get_all_links,
    has_node,
    get_roots,
    get_leaves,
    get_related_nodes,
    get_links_for_node,
)

# Filters - filtering operations
from .filters import (
    filter_by_type,
    filter_links_by_polarity,
    filter_by_base_rate,
    filter_nodes,
    filter_links,
)

# Traversal - path and tree operations
from .traversal import (
    get_ancestors,
    get_descendants,
    get_depth,
    get_height,
    get_paths,
    get_shortest_path,
    get_subgraph,
    topological_sort,
    extract_support_subgraph,
    extract_paths_subgraph,
    extract_connected_component,
)

# Analysis - computed properties
from .analysis import (
    compute_graph_stats,
    find_ungrounded_claims,
    find_weakly_supported,
    check_acyclic,
    find_cycles,
    find_isolated_nodes,
    get_links_targeting_links,
)

# Serialization
from .serialize import graph_to_dict

# Textual - source text grounding
from .textual import (
    get_textual_basis,
    get_quoted_text,
    get_all_quoted_texts,
    find_text_in_source,
    get_nodes_at_position,
    get_nodes_in_span,
    compute_grounding_coverage,
    get_grounding_gaps,
    compute_grounding_stats,
)

__all__ = [
    # Queries
    "get_node",
    "get_link",
    "get_all_nodes",
    "get_all_links",
    "has_node",
    "get_roots",
    "get_leaves",
    "get_related_nodes",
    "get_links_for_node",
    # Filters
    "filter_by_type",
    "filter_links_by_polarity",
    "filter_by_base_rate",
    "filter_nodes",
    "filter_links",
    # Traversal
    "get_ancestors",
    "get_descendants",
    "get_depth",
    "get_height",
    "get_paths",
    "get_shortest_path",
    "get_subgraph",
    "topological_sort",
    "extract_support_subgraph",
    "extract_paths_subgraph",
    "extract_connected_component",
    # Analysis
    "compute_graph_stats",
    "find_ungrounded_claims",
    "find_weakly_supported",
    "check_acyclic",
    "find_cycles",
    "find_isolated_nodes",
    "get_links_targeting_links",
    # Serialization
    "graph_to_dict",
    # Textual
    "get_textual_basis",
    "get_quoted_text",
    "get_all_quoted_texts",
    "find_text_in_source",
    "get_nodes_at_position",
    "get_nodes_in_span",
    "compute_grounding_coverage",
    "get_grounding_gaps",
    "compute_grounding_stats",
]
