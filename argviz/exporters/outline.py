"""Outline format exporter for argument graphs."""

from __future__ import annotations

import re
import secrets
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from argviz.model import GraphModel


class OutlineParseError(Exception):
    """Raised when outline parsing fails."""

    def __init__(self, line_number: int, message: str):
        self.line_number = line_number
        self.message = message
        super().__init__(f"Line {line_number}: {message}")


@dataclass
class ParsedLine:
    """A parsed outline line."""

    line_number: int
    indent_level: int
    number: str
    polarity: str | None
    node_type: str
    content: str | None
    backref: str | None
    is_warrant: bool


class OutlineParser:
    """Parse hierarchical outline format back into argument graphs."""

    # Regex for standard lines: indent + number + [bracket] + optional [bracket] + content
    LINE_PATTERN = re.compile(
        r'^(\s*)'                           # Group 1: indentation
        r'(\d+(?:\.\d+)*(?:w\d+)?)'          # Group 2: number (e.g., "1.1.2" or "1.1w1")
        r'\.?\s+'                            # Optional period (for conclusions), whitespace
        r'\[([^\]]+)\]'                      # Group 3: first bracket
        r'(?:\s+\[([^\]]+)\])?'              # Group 4: optional second bracket
        r'\s+'                               # Whitespace
        r'(.+)$'                             # Group 5: content or back-reference
    )

    # Regex for back-reference content
    BACKREF_PATTERN = re.compile(r'^\(see\s+(\d+(?:\.\d+)*)\)$')

    def _parse_line(self, line: str, line_number: int) -> ParsedLine:
        """Parse a single outline line.

        Args:
            line: The line text to parse.
            line_number: Line number for error reporting.

        Returns:
            ParsedLine with extracted components.

        Raises:
            OutlineParseError: If line is malformed.
        """
        match = self.LINE_PATTERN.match(line)
        if not match:
            raise OutlineParseError(line_number, f"Malformed line: '{line}'")

        indent_str, number, bracket1, bracket2, content_or_ref = match.groups()

        # Validate indentation
        indent_len = len(indent_str)
        if indent_len % 3 != 0:
            raise OutlineParseError(
                line_number,
                f"Invalid indentation: expected multiple of 3 spaces, got {indent_len}"
            )
        indent_level = indent_len // 3

        # Determine if this is a warrant (has 'w' in number)
        is_warrant = 'w' in number

        # Parse bracket contents
        # For conclusions: bracket1 = "Conclusion", bracket2 = None
        # For others: bracket1 = polarity, bracket2 = type
        if bracket1 == "Conclusion":
            polarity = None
            node_type = "Conclusion"
            content = content_or_ref
            backref = None
        else:
            polarity = bracket1
            node_type = bracket2 if bracket2 else "Proposition"

            # Check if content is a back-reference
            backref_match = self.BACKREF_PATTERN.match(content_or_ref)
            if backref_match:
                backref = backref_match.group(1)
                content = None
            else:
                backref = None
                content = content_or_ref

        return ParsedLine(
            line_number=line_number,
            indent_level=indent_level,
            number=number,
            polarity=polarity,
            node_type=node_type,
            content=content,
            backref=backref,
            is_warrant=is_warrant,
        )

    def _get_parent_number(self, number: str) -> str | None:
        """Get the parent outline number from a child number.

        Args:
            number: An outline number like "1.2.3" or "1.2w1".

        Returns:
            The parent number (e.g., "1.2" for "1.2.3") or None for root.
        """
        # Handle warrant numbers like "1.2w1" -> parent is "1.2"
        if 'w' in number:
            return number.split('w')[0]

        parts = number.split('.')
        if len(parts) <= 1:
            return None
        return '.'.join(parts[:-1])

    def parse(self, text: str) -> GraphModel:
        """Parse an outline string into a GraphModel.

        Args:
            text: The outline text to parse.

        Returns:
            A GraphModel representing the argument graph.

        Raises:
            OutlineParseError: If parsing fails.
        """
        # Parse all non-empty lines
        lines = text.split('\n')
        parsed_lines: list[ParsedLine] = []

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            parsed = self._parse_line(line, i)
            parsed_lines.append(parsed)

        if not parsed_lines:
            return GraphModel({"nodes": [], "links": [], "edges": []})

        # Maps outline number -> node_id
        number_to_node_id: dict[str, str] = {}

        # Build nodes and links
        nodes: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        # First pass: create nodes for all non-backref, non-warrant lines
        for parsed in parsed_lines:
            if parsed.backref is not None:
                # Back-references don't create new nodes
                continue
            if parsed.is_warrant:
                # Warrants handled separately in fourth pass
                continue

            # Generate unique node ID
            node_id = f"node_{secrets.token_hex(4)}"
            number_to_node_id[parsed.number] = node_id

            node = {
                "id": node_id,
                "type": parsed.node_type,
                "content": parsed.content,
            }
            nodes.append(node)

        # Also create warrant nodes
        for parsed in parsed_lines:
            if parsed.backref is not None:
                continue
            if not parsed.is_warrant:
                continue

            # Generate unique node ID for warrant
            node_id = f"node_{secrets.token_hex(4)}"
            number_to_node_id[parsed.number] = node_id

            node = {
                "id": node_id,
                "type": parsed.node_type,
                "content": parsed.content,
            }
            nodes.append(node)

        # Second pass: determine links and co-premises
        # Co-premise detection: items whose parent number DOESN'T exist as a node
        # are co-premises targeting their grandparent.
        # Items whose parent EXISTS as a node are single-source links (created immediately).
        #
        # Example: 1.1.1.1, 1.1.1.2 have parent "1.1.1" which doesn't exist
        #          -> they are co-premises targeting "1.1"
        #          1.1, 1.2 have parent "1" which exists -> separate links to "1"

        # Key: (grandparent_number, polarity) -> list of parsed lines (for co-premises only)
        copremise_groups: dict[tuple[str, str], list[ParsedLine]] = defaultdict(list)
        # Track number_to_link_id for warrant targeting (built during link creation)
        number_to_link_id: dict[str, str] = {}

        for parsed in parsed_lines:
            # Skip conclusions (they have no parent to link to)
            if parsed.node_type == "Conclusion":
                continue
            # Skip warrants (handled in fourth pass)
            if parsed.is_warrant:
                continue

            parent_number = self._get_parent_number(parsed.number)
            if parent_number is None:
                continue

            # Determine the source node
            if parsed.backref is not None:
                source_node_id = number_to_node_id.get(parsed.backref)
                if source_node_id is None:
                    raise OutlineParseError(
                        parsed.line_number,
                        f"Back-reference '{parsed.backref}' not found"
                    )
            else:
                source_node_id = number_to_node_id.get(parsed.number)

            if source_node_id is None:
                continue

            # Check if parent exists as a node
            parent_exists = parent_number in number_to_node_id

            if parent_exists:
                # Parent exists -> create a separate single-source link immediately
                target_node_id = number_to_node_id[parent_number]

                # Create single-source link
                polarity = parsed.polarity or "supports"
                link_id = f"link_{secrets.token_hex(4)}"
                link = {
                    "id": link_id,
                    "source_ids": [source_node_id],
                    "target_id": target_node_id,
                    "polarity": polarity,
                }
                links.append(link)
                # Track for warrant targeting
                number_to_link_id[parsed.number] = link_id
            else:
                # Parent doesn't exist -> this is a co-premise
                # Target is the grandparent (parent of parent)
                grandparent = self._get_parent_number(parent_number)
                if grandparent is None:
                    continue
                if grandparent not in number_to_node_id:
                    continue

                # Group for co-premise linking
                # Key by parent_number (not grandparent) to keep distinct co-premise sets separate
                # e.g., 1.2.1.x and 1.2.2.x are different groups even though they share grandparent 1.2
                polarity = parsed.polarity or "supports"
                key = (parent_number, polarity)
                copremise_groups[key].append(parsed)

        # Third pass: create links from co-premise groups (multiple sources per link)
        for (parent_number, polarity), siblings in copremise_groups.items():
            # The key is parent_number (which doesn't exist as a node), so target is grandparent
            grandparent = self._get_parent_number(parent_number)
            if grandparent is None:
                continue
            target_node_id = number_to_node_id.get(grandparent)
            if target_node_id is None:
                continue

            # Collect all source node IDs for this group
            source_ids: list[str] = []
            first_source_number: str | None = None

            for parsed in siblings:
                if parsed.backref is not None:
                    source_node_id = number_to_node_id.get(parsed.backref)
                else:
                    source_node_id = number_to_node_id.get(parsed.number)

                if source_node_id is not None:
                    source_ids.append(source_node_id)
                    if first_source_number is None:
                        first_source_number = parsed.number

            if not source_ids:
                continue

            # Create a single link with all sources
            link_id = f"link_{secrets.token_hex(4)}"
            link = {
                "id": link_id,
                "source_ids": source_ids,
                "target_id": target_node_id,
                "polarity": polarity,
            }
            links.append(link)

            # Store link_id keyed by first source's number for warrant targeting
            if first_source_number is not None:
                number_to_link_id[first_source_number] = link_id

        # Fourth pass: create warrant links (must come after regular links exist)
        for parsed in parsed_lines:
            if not parsed.is_warrant:
                continue
            if parsed.backref is not None:
                # Back-reference warrants - source is the referenced node
                source_node_id = number_to_node_id.get(parsed.backref)
            else:
                source_node_id = number_to_node_id.get(parsed.number)

            if source_node_id is None:
                continue

            # Warrants target the link whose first source matches their parent number
            # e.g., 1.1w1 targets link from 1.1
            parent_number = self._get_parent_number(parsed.number)
            if parent_number is None:
                continue

            target_link_id = number_to_link_id.get(parent_number)
            if target_link_id is None:
                continue

            # Create warrant link targeting the link
            warrant_link_id = f"link_{secrets.token_hex(4)}"
            warrant_link = {
                "id": warrant_link_id,
                "source_ids": [source_node_id],
                "target_id": target_link_id,
                "polarity": "supports",  # Warrants support the inference
            }
            links.append(warrant_link)

        return GraphModel({"nodes": nodes, "links": links, "edges": edges})

    def parse_from_file(self, path: Path) -> GraphModel:
        """Parse outline from a file.

        Args:
            path: Path to outline text file.

        Returns:
            GraphModel reconstructed from the outline.

        Raises:
            OutlineParseError: If the outline is malformed.
            FileNotFoundError: If the file doesn't exist.
        """
        with open(path) as f:
            text = f.read()
        return self.parse(text)


class OutlineExporter:
    """Export argument graphs to hierarchical numbered outline format."""

    def export(self, model: GraphModel) -> str:
        """Export graph to outline text.

        Args:
            model: The argument graph to export.

        Returns:
            Hierarchical numbered outline string.
        """
        # Find all conclusions (root nodes)
        conclusions = [
            (node_id, node)
            for node_id, node in model.nodes.items()
            if node.get("type") == "Conclusion"
        ]

        # Sort for deterministic output
        conclusions.sort(key=lambda x: x[1].get("content", x[0]))

        # Track first occurrence of each node for back-references
        self._node_registry: dict[str, str] = {}

        sections = []
        for i, (conclusion_id, conclusion) in enumerate(conclusions, start=1):
            section = self._format_conclusion_tree(
                model, conclusion_id, conclusion, str(i)
            )
            sections.append(section)

        return "\n\n".join(sections)

    def _format_conclusion_tree(
        self,
        model: GraphModel,
        node_id: str,
        node: dict[str, Any],
        number: str,
    ) -> str:
        """Format a conclusion and its supporting tree."""
        lines = []
        content = node.get("content", node_id)
        lines.append(f"{number}. [Conclusion] {content}")

        # Register this node
        self._node_registry[node_id] = number

        child_index = 1

        # Find incoming links (supporters/underminers)
        incoming_links = model.get_incoming_links(node_id)

        # Sort for deterministic output
        incoming_links.sort(key=lambda lnk: (lnk.get("polarity", ""), lnk.get("id", "")))

        for link in incoming_links:
            child_number = f"{number}.{child_index}"
            child_lines = self._format_link_subtree(model, link, child_number, indent=1)
            lines.extend(child_lines)
            child_index += 1

        return "\n\n".join(lines)

    def _format_link_subtree(
        self,
        model: GraphModel,
        link: dict[str, Any],
        number: str,
        indent: int,
    ) -> list[str]:
        """Format a link and its source nodes."""
        lines = []
        polarity = link.get("polarity", "supports")
        source_ids = link.get("source_ids", [])
        link_id = link.get("id")

        # Process each source node
        for k, source_id in enumerate(source_ids):
            if len(source_ids) > 1:
                source_number = f"{number}.{k + 1}"
            else:
                source_number = number

            # Check for back-reference
            if source_id in self._node_registry:
                existing_number = self._node_registry[source_id]
                indent_str = "   " * indent
                lines.append(f"{indent_str}{source_number} [{polarity}] (see {existing_number})")
                continue

            source_node = model.nodes.get(source_id)
            if source_node:
                line = self._format_node_line(source_node, source_id, polarity, source_number, indent)
                lines.append(line)
                self._node_registry[source_id] = source_number

                # Recurse into this node's supporters
                child_lines = self._get_children_lines(model, source_id, source_number, indent + 1)
                lines.extend(child_lines)

        # Add warrants (links that target this link)
        if link_id:
            warrant_lines = self._get_warrant_lines(model, link_id, number, indent)
            lines.extend(warrant_lines)

        return lines

    def _get_warrant_lines(
        self,
        model: GraphModel,
        link_id: str,
        parent_number: str,
        indent: int,
    ) -> list[str]:
        """Get formatted lines for warrants supporting a link."""
        lines = []

        # Find links that target this link (warrants)
        warrant_links = [
            lnk for lnk in model.links.values()
            if lnk.get("target_id") == link_id
        ]

        # Sort for deterministic output
        warrant_links.sort(key=lambda lnk: (lnk.get("polarity", ""), lnk.get("id", "")))

        warrant_index = 1
        for warrant_link in warrant_links:
            source_ids = warrant_link.get("source_ids", [])
            for source_id in source_ids:
                warrant_number = f"{parent_number}w{warrant_index}"

                # Check for back-reference
                if source_id in self._node_registry:
                    existing_number = self._node_registry[source_id]
                    indent_str = "   " * indent
                    lines.append(f"{indent_str}{warrant_number} [warrant] (see {existing_number})")
                    warrant_index += 1
                    continue

                source_node = model.nodes.get(source_id)
                if source_node:
                    indent_str = "   " * indent
                    node_type = source_node.get("type", "Proposition")
                    content = source_node.get("content", source_id)
                    lines.append(f"{indent_str}{warrant_number} [warrant] [{node_type}] {content}")
                    self._node_registry[source_id] = warrant_number

                    # Recurse into this warrant's supporters
                    child_lines = self._get_children_lines(model, source_id, warrant_number, indent + 1)
                    lines.extend(child_lines)
                    warrant_index += 1

        return lines

    def _format_node_line(
        self,
        node: dict[str, Any],
        node_id: str,
        polarity: str,
        number: str,
        indent: int,
    ) -> str:
        """Format a single node line."""
        indent_str = "   " * indent
        node_type = node.get("type", "Proposition")
        content = node.get("content", node_id)
        return f"{indent_str}{number} [{polarity}] [{node_type}] {content}"

    def _get_children_lines(
        self,
        model: GraphModel,
        node_id: str,
        parent_number: str,
        indent: int,
    ) -> list[str]:
        """Get formatted lines for all children of a node."""
        lines = []
        child_index = 1

        # Handle incoming links (supports/undermines)
        incoming_links = model.get_incoming_links(node_id)
        incoming_links.sort(key=lambda lnk: (lnk.get("polarity", ""), lnk.get("id", "")))

        for link in incoming_links:
            child_number = f"{parent_number}.{child_index}"
            child_lines = self._format_link_subtree(model, link, child_number, indent)
            lines.extend(child_lines)
            child_index += 1

        return lines

    def export_to_file(self, model: GraphModel, path: Path) -> None:
        """Export graph to a file.

        Args:
            model: The argument graph to export.
            path: Output file path.
        """
        content = self.export(model)
        with open(path, "w") as f:
            f.write(content)
