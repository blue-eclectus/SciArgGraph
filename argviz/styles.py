"""Style registry for argument graph visualization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class NodeStyle:
    """Visual properties for a node."""
    shape: str
    fill_color: str
    border_color: str
    border_width: float = 1.0
    font_family: str = "Helvetica"
    font_size: float = 10.0
    width: float | None = None
    height: float | None = None
    fixed_size: bool = False


@dataclass
class EdgeStyle:
    """Visual properties for an edge."""
    line_color: str
    line_width: float = 1.5
    line_style: str = "solid"  # solid, dashed, dotted
    arrow_shape: str = "normal"


# Default color palette
COLORS = {
    "proposition_fill": "#6FB1FC",
    "proposition_border": "#4A90D9",
    "proposition_implicit_fill": "#C2E0FF",  # Lighter blue for implicit co-premises
    "proposition_implicit_border": "#A8CCF0",
    "conclusion_fill": "#FFD700",  # Gold - emphasizes terminal/final claims
    "conclusion_border": "#DAA520",  # Goldenrod
    "datum_fill": "#F5A45D",
    "datum_border": "#D4843D",
    "link_supports_fill": "#7FC97F",
    "link_supports_border": "#5A9A5A",
    "link_undermines_fill": "#E74C3C",
    "link_undermines_border": "#C0392B",
    "edge_default": "#333333",
}

# Default max characters before truncation
DEFAULT_MAX_LABEL_CHARS = 100

# Pattern for valid hex colors (#RGB or #RRGGBB)
_HEX_COLOR_PATTERN = re.compile(r'^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$')


def _validate_colors(colors: dict[str, str]) -> None:
    """Validate that all color values are valid hex colors.

    Args:
        colors: Dictionary of color name -> color value.

    Raises:
        ValueError: If any color value is invalid.
    """
    for key, value in colors.items():
        if not _HEX_COLOR_PATTERN.match(value):
            raise ValueError(
                f"Invalid color '{value}' for key '{key}'. "
                "Expected hex format (#RGB or #RRGGBB)."
            )


def _load_theme(theme_path: str | None) -> dict[str, str]:
    """Load theme colors from YAML file.

    Args:
        theme_path: Path to theme YAML file, or None for bundled default.

    Returns:
        Dictionary of color name -> hex color.

    Raises:
        FileNotFoundError: If theme file doesn't exist.
        ValueError: If any color value is invalid.
    """
    if theme_path is None:
        # Load bundled default theme
        try:
            from importlib import resources
            theme_file = resources.files("argviz.themes").joinpath("default.yaml")
            content = theme_file.read_text()
        except (FileNotFoundError, TypeError):
            # Fallback to hardcoded defaults
            return dict(COLORS)
    else:
        path = Path(theme_path)
        if not path.exists():
            raise FileNotFoundError(f"Theme file not found: {theme_path}")
        content = path.read_text()

    import yaml
    data = yaml.safe_load(content)
    colors = data.get("colors", {})
    _validate_colors(colors)
    return colors


def truncate_label(text: str, max_chars: int = DEFAULT_MAX_LABEL_CHARS) -> tuple[str, bool]:
    """Truncate text with ellipsis if it exceeds max_chars.

    Attempts to truncate at word boundaries when possible.

    Args:
        text: The text to potentially truncate.
        max_chars: Maximum characters before truncation (content before ellipsis).

    Returns:
        Tuple of (truncated_text, was_truncated).
        If truncated, text ends with Unicode ellipsis (…).
    """
    if len(text) <= max_chars:
        return text, False

    # Try to truncate at word boundary
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")

    if last_space > 0:
        # Found a space - truncate at word boundary
        truncated = truncated[:last_space]

    return truncated + "…", True


class StyleRegistry:
    """Map node/edge types to visual properties."""

    def __init__(
        self,
        theme: str | None = None,
        max_label_chars: int = DEFAULT_MAX_LABEL_CHARS,
    ) -> None:
        """Initialize style registry.

        Args:
            theme: Path to theme YAML file. Uses bundled default if None.
            max_label_chars: Maximum label length before truncation.
        """
        self._colors = _load_theme(theme)
        self.max_label_chars = max_label_chars

    def _get_color(self, key: str) -> str:
        """Get color from theme, falling back to COLORS default.

        Args:
            key: Theme color key (e.g., 'proposition', 'datum').

        Returns:
            Hex color string.
        """
        # Map theme keys to COLORS keys
        theme_to_default = {
            "proposition": "proposition_fill",
            "proposition_implicit": "proposition_implicit_fill",
            "conclusion": "conclusion_fill",
            "datum": "datum_fill",
            "link_supports": "link_supports_fill",
            "link_undermines": "link_undermines_fill",
            "proposition_border": "proposition_border",
            "proposition_implicit_border": "proposition_implicit_border",
            "conclusion_border": "conclusion_border",
            "datum_border": "datum_border",
            "link_supports_border": "link_supports_border",
            "link_undermines_border": "link_undermines_border",
            "edge_supports": "link_supports_border",
            "edge_undermines": "link_undermines_border",
            "edge_default": "edge_default",
            "background": "background",
        }
        # Default background to white if not in theme or COLORS
        default_key = theme_to_default.get(key, key)
        fallback = "#FFFFFF" if key == "background" else "#000000"
        return self._colors.get(key, COLORS.get(default_key, fallback))

    def get_node_style(
        self, node: dict[str, Any], is_link: bool = False
    ) -> NodeStyle:
        """Get visual style for a node.

        Args:
            node: Node data dictionary.
            is_link: Whether this is a Link node (reified relationship).

        Returns:
            NodeStyle with visual properties.
        """
        if is_link:
            return self._get_link_style(node)

        node_type = node.get("type", "Proposition")

        if node_type == "Datum":
            return NodeStyle(
                shape="ellipse",
                fill_color=self._get_color("datum"),
                border_color=self._get_color("datum_border"),
            )
        elif node_type == "Conclusion":
            # Conclusion: same shape as Proposition, but gold to indicate terminal claim
            return NodeStyle(
                shape="box",
                fill_color=self._get_color("conclusion"),
                border_color=self._get_color("conclusion_border"),
            )
        else:  # Proposition or unknown
            # Check if this is an implicit/inferred proposition
            # "implicit" = assumed co-premise from stems
            # "inferred" = synthesized auxiliary from MSA iteration
            # Both represent claims not explicitly stated in source text
            explicitness = node.get("explicitness")
            if explicitness in ("implicit", "inferred"):
                return NodeStyle(
                    shape="box",
                    fill_color=self._get_color("proposition_implicit"),
                    border_color=self._get_color("proposition_implicit_border"),
                )
            return NodeStyle(
                shape="box",
                fill_color=self._get_color("proposition"),
                border_color=self._get_color("proposition_border"),
            )

    def _get_link_style(self, link: dict[str, Any]) -> NodeStyle:
        """Get style for a Link node."""
        polarity = link.get("polarity", "supports")

        if polarity == "undermines":
            return NodeStyle(
                shape="diamond",
                fill_color=self._get_color("link_undermines"),
                border_color=self._get_color("link_undermines_border"),
                width=0.3,
                height=0.3,
                fixed_size=True,
            )
        else:  # supports
            return NodeStyle(
                shape="diamond",
                fill_color=self._get_color("link_supports"),
                border_color=self._get_color("link_supports_border"),
                width=0.3,
                height=0.3,
                fixed_size=True,
            )

    def get_link_edge_style(self, link: dict[str, Any]) -> EdgeStyle:
        """Get visual style for edges connecting through a Link node.

        Args:
            link: Link data dictionary with 'polarity' field.

        Returns:
            EdgeStyle with visual properties.
        """
        polarity = link.get("polarity", "supports")

        if polarity == "undermines":
            return EdgeStyle(
                line_color=self._get_color("edge_undermines"),
                line_style="dashed",
            )
        else:  # supports
            return EdgeStyle(
                line_color=self._get_color("edge_supports"),
                line_style="solid",
            )

