"""Source text grounding queries for argument graphs.

Note: The current TextualBasis model uses quoted text with optional location
strings, not character position spans. Position-based queries work by searching
for the quoted text in the source document.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from argviz.model import GraphModel

# Type aliases
NodeId = str
TextualBasis = dict[str, Any] | list[dict[str, Any]] | None


def _normalize_textual_basis(tb: Any) -> list[dict[str, Any]]:
    """Normalize textual basis to a list of span dicts.

    TextualBasis can be:
    - None
    - A single dict with 'text' and optional 'location'
    - A list of such dicts

    Returns:
        List of span dicts, empty if None.
    """
    if tb is None:
        return []
    if isinstance(tb, list):
        return tb
    if isinstance(tb, dict):
        return [tb]
    return []


def get_textual_basis(graph: GraphModel, node_id: NodeId) -> TextualBasis:
    """Get the TextualBasis for a node.

    Args:
        graph: The argument graph.
        node_id: Node to get grounding for.

    Returns:
        TextualBasis (dict, list of dicts, or None) if found.
    """
    node = graph.nodes.get(node_id)
    if node is None:
        return None
    return node.get("textual_basis")


def get_quoted_text(graph: GraphModel, node_id: NodeId) -> str | None:
    """Get the quoted source text for a node.

    If the node has multiple TextualBasis spans, returns the first one.

    Args:
        graph: The argument graph.
        node_id: Node to get quoted text for.

    Returns:
        Quoted text string, or None if ungrounded.
    """
    tb = get_textual_basis(graph, node_id)
    spans = _normalize_textual_basis(tb)

    if not spans:
        return None

    return spans[0].get("text")


def get_all_quoted_texts(graph: GraphModel, node_id: NodeId) -> list[str]:
    """Get all quoted source texts for a node.

    Args:
        graph: The argument graph.
        node_id: Node to get quoted texts for.

    Returns:
        List of quoted text strings. Empty if ungrounded.
    """
    tb = get_textual_basis(graph, node_id)
    spans = _normalize_textual_basis(tb)

    return [span.get("text", "") for span in spans if span.get("text")]


def find_text_in_source(
    source_text: str,
    quoted_text: str,
) -> tuple[int, int] | None:
    """Find the position of quoted text in source document.

    Args:
        source_text: The full source document.
        quoted_text: The text to find.

    Returns:
        Tuple of (start, end) character positions, or None if not found.
    """
    idx = source_text.find(quoted_text)
    if idx == -1:
        return None
    return (idx, idx + len(quoted_text))


def get_nodes_at_position(
    graph: GraphModel,
    source_text: str,
    position: int,
) -> list[NodeId]:
    """Find nodes whose quoted text contains this character position.

    Searches for each node's quoted text in the source and checks
    if the position falls within that range.

    Args:
        graph: The argument graph.
        source_text: The original source document.
        position: Character position in source text.

    Returns:
        List of node IDs whose grounded text contains this position.
    """
    result: list[NodeId] = []

    for node_id in graph.nodes:
        for quoted in get_all_quoted_texts(graph, node_id):
            span = find_text_in_source(source_text, quoted)
            if span and span[0] <= position < span[1]:
                result.append(node_id)
                break  # Don't add same node twice

    return result


def get_nodes_in_span(
    graph: GraphModel,
    source_text: str,
    start: int,
    end: int,
) -> list[NodeId]:
    """Find nodes grounded in a character range.

    Returns nodes whose quoted text overlaps [start, end).

    Args:
        graph: The argument graph.
        source_text: The original source document.
        start: Start character position (inclusive).
        end: End character position (exclusive).

    Returns:
        List of node IDs with spans overlapping the range.
    """
    result: list[NodeId] = []

    for node_id in graph.nodes:
        for quoted in get_all_quoted_texts(graph, node_id):
            span = find_text_in_source(source_text, quoted)
            if span:
                # Check for overlap: not (span ends before range or range ends before span)
                if not (span[1] <= start or end <= span[0]):
                    result.append(node_id)
                    break

    return result


def compute_grounding_coverage(
    graph: GraphModel,
    source_text: str,
) -> float:
    """Compute what fraction of source text is covered by node spans.

    Args:
        graph: The argument graph.
        source_text: The original source document.

    Returns:
        Coverage ratio 0-1. Overlapping spans counted once.
    """
    if not source_text:
        return 0.0

    source_length = len(source_text)

    # Collect all spans
    spans: list[tuple[int, int]] = []
    for node_id in graph.nodes:
        for quoted in get_all_quoted_texts(graph, node_id):
            span = find_text_in_source(source_text, quoted)
            if span:
                spans.append(span)

    if not spans:
        return 0.0

    # Merge overlapping spans to avoid double-counting
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            # Overlaps with previous - extend it
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Sum coverage
    covered = sum(end - start for start, end in merged)
    return covered / source_length


def get_grounding_gaps(
    graph: GraphModel,
    source_text: str,
    min_gap_size: int = 50,
) -> list[tuple[int, int]]:
    """Find ranges of source text not covered by any node span.

    Args:
        graph: The argument graph.
        source_text: The original source document.
        min_gap_size: Minimum gap size to report (filters noise).

    Returns:
        List of (start, end) tuples for uncovered ranges.
    """
    if not source_text:
        return []

    source_length = len(source_text)

    # Collect and merge all spans
    spans: list[tuple[int, int]] = []
    for node_id in graph.nodes:
        for quoted in get_all_quoted_texts(graph, node_id):
            span = find_text_in_source(source_text, quoted)
            if span:
                spans.append(span)

    if not spans:
        if source_length >= min_gap_size:
            return [(0, source_length)]
        return []

    # Merge overlapping spans
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Find gaps
    gaps: list[tuple[int, int]] = []

    # Gap before first span
    if merged[0][0] >= min_gap_size:
        gaps.append((0, merged[0][0]))

    # Gaps between spans
    for i in range(len(merged) - 1):
        gap_start = merged[i][1]
        gap_end = merged[i + 1][0]
        if gap_end - gap_start >= min_gap_size:
            gaps.append((gap_start, gap_end))

    # Gap after last span
    if source_length - merged[-1][1] >= min_gap_size:
        gaps.append((merged[-1][1], source_length))

    return gaps


def compute_grounding_stats(
    graph: GraphModel,
    source_text: str,
) -> dict[str, Any]:
    """Compute comprehensive grounding statistics.

    Args:
        graph: The argument graph.
        source_text: The original source document.

    Returns:
        Dict with keys:
        - grounded_node_count: Nodes with TextualBasis
        - ungrounded_node_count: Nodes without TextualBasis
        - coverage_ratio: Fraction of source covered
        - avg_span_length: Average text span length
        - grounded_by_type: Dict mapping NodeType to grounded count
    """
    grounded_count = 0
    ungrounded_count = 0
    grounded_by_type: dict[str, int] = {}
    span_lengths: list[int] = []

    for node_id, node in graph.nodes.items():
        tb = node.get("textual_basis")
        node_type = node.get("type", "Unknown")

        if tb:
            grounded_count += 1
            grounded_by_type[node_type] = grounded_by_type.get(node_type, 0) + 1

            # Collect span lengths
            spans = _normalize_textual_basis(tb)
            for span in spans:
                text = span.get("text", "")
                if text:
                    span_lengths.append(len(text))
        else:
            ungrounded_count += 1

    avg_span_length = (
        sum(span_lengths) / len(span_lengths) if span_lengths else 0.0
    )

    return {
        "grounded_node_count": grounded_count,
        "ungrounded_node_count": ungrounded_count,
        "coverage_ratio": compute_grounding_coverage(graph, source_text),
        "avg_span_length": round(avg_span_length, 1),
        "grounded_by_type": grounded_by_type,
    }
