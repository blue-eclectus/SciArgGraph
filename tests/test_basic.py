"""Basic smoke tests for argviz."""

import pytest
from pathlib import Path

from argviz import load, visualize
from argviz.graph_utils import (
    get_leaves,
    get_roots,
    get_ancestors,
    filter_by_type,
    compute_graph_stats,
    check_acyclic,
)


EXAMPLE_PATH = Path(__file__).parent.parent / "examples" / "argument_graph.yaml"


class TestLoad:
    """Test loading argument graphs."""

    def test_load_example(self):
        model = load(EXAMPLE_PATH)
        assert len(model.nodes) > 0
        assert len(model.links) > 0

    def test_nodes_have_required_fields(self):
        model = load(EXAMPLE_PATH)
        for node_id, node in model.nodes.items():
            assert "id" in node
            assert "type" in node
            assert "content" in node


class TestExport:
    """Test export formats."""

    def test_export_dot(self):
        output = visualize(EXAMPLE_PATH, format="dot")
        assert "digraph" in output
        assert len(output) > 100

    def test_export_cytoscape_json(self):
        output = visualize(EXAMPLE_PATH, format="cytoscape-json")
        assert "elements" in output
        assert "nodes" in output

    def test_export_cytoscape_html(self):
        output = visualize(EXAMPLE_PATH, format="cytoscape-html")
        assert "<html>" in output.lower()
        assert "cytoscape" in output.lower()

    @pytest.mark.skipif(
        not pytest.importorskip("subprocess").run(
            ["which", "dot"], capture_output=True
        ).returncode == 0,
        reason="Graphviz not installed",
    )
    def test_export_svg(self):
        output = visualize(EXAMPLE_PATH, format="svg")
        assert "<svg" in output.lower()


class TestGraphUtils:
    """Test graph utility functions."""

    def test_get_leaves(self):
        model = load(EXAMPLE_PATH)
        leaves = get_leaves(model)
        assert len(leaves) > 0

    def test_get_roots(self):
        model = load(EXAMPLE_PATH)
        roots = get_roots(model)
        assert len(roots) > 0

    def test_get_ancestors(self):
        model = load(EXAMPLE_PATH)
        # Get a non-leaf node to find ancestors for
        roots = get_roots(model)
        if roots:
            ancestors = get_ancestors(model, roots[0])
            # Ancestors may be empty for root, that's ok
            assert isinstance(ancestors, (list, set))

    def test_filter_by_type(self):
        model = load(EXAMPLE_PATH)
        datums = filter_by_type(model, "Datum")
        assert len(datums) > 0
        conclusions = filter_by_type(model, "Conclusion")
        assert len(conclusions) > 0

    def test_compute_graph_stats(self):
        model = load(EXAMPLE_PATH)
        stats = compute_graph_stats(model)
        assert isinstance(stats, dict)

    def test_check_acyclic(self):
        model = load(EXAMPLE_PATH)
        is_acyclic = check_acyclic(model)
        assert is_acyclic is True


class TestSubgraph:
    """Test subgraph extraction."""

    def test_get_subgraph(self):
        model = load(EXAMPLE_PATH)
        # Get subgraph around the conclusion
        subgraph = model.get_subgraph("C1", depth_up=2, depth_down=0)
        assert len(subgraph.nodes) >= 1


class TestStrengthField:
    """Test the strength field on Links (renamed from reliability)."""

    def test_links_have_strength_field(self):
        model = load(EXAMPLE_PATH)
        for link_id, link in model.links.items():
            assert "strength" in link, f"Link {link_id} missing strength field"
            assert 0 <= link["strength"] <= 1

    def test_strength_in_pydantic_model(self):
        from argviz.types import Link
        link = Link(
            id="test",
            source_ids=["A"],
            target_id="B",
            polarity="supports",
            strength=0.7,
        )
        assert link.strength == 0.7

    def test_strength_default_value(self):
        from argviz.types import Link
        link = Link(
            id="test",
            source_ids=["A"],
            target_id="B",
            polarity="supports",
        )
        assert link.strength == 0.8  # Default value


class TestAuxiliaryField:
    """Test the auxiliary field on Propositions."""

    def test_auxiliary_nodes_exist(self):
        model = load(EXAMPLE_PATH)
        auxiliary_nodes = [
            node_id for node_id, node in model.nodes.items()
            if node.get("auxiliary", False)
        ]
        assert len(auxiliary_nodes) > 0, "Example should have auxiliary nodes"

    def test_auxiliary_in_pydantic_model(self):
        from argviz.types import Proposition
        prop = Proposition(
            id="test",
            content="Test proposition",
            auxiliary=True,
        )
        assert prop.auxiliary is True

    def test_auxiliary_default_false(self):
        from argviz.types import Proposition
        prop = Proposition(
            id="test",
            content="Test proposition",
        )
        assert prop.auxiliary is False

    def test_auxiliary_edges_dashed_in_dot(self):
        """Auxiliary nodes should have dashed edges in DOT output."""
        model = load(EXAMPLE_PATH)
        dot_output = visualize(EXAMPLE_PATH, format="dot")
        # DOT format uses style=dashed for auxiliary edges
        assert "dashed" in dot_output, "DOT output should have dashed edges for auxiliary nodes"


class TestSchemaValidation:
    """Test that invalid input is rejected."""

    def test_missing_required_field_raises(self):
        from argviz.parser import YAMLParser
        import tempfile

        # Missing 'content' field on Proposition
        invalid_yaml = """
nodes:
  - type: Proposition
    id: P1
"""
        parser = YAMLParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(invalid_yaml)
            f.flush()
            with pytest.raises(Exception):  # Schema validation error
                parser.parse(f.name)

    def test_missing_source_on_datum_raises(self):
        from argviz.parser import YAMLParser
        import tempfile

        # Datum requires 'source' field
        invalid_yaml = """
nodes:
  - type: Datum
    id: D1
    content: "Some finding"
"""
        parser = YAMLParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(invalid_yaml)
            f.flush()
            with pytest.raises(Exception):
                parser.parse(f.name)

    def test_invalid_polarity_raises(self):
        from argviz.types import Link
        with pytest.raises(Exception):
            Link(
                id="test",
                source_ids=["A"],
                target_id="B",
                polarity="invalid_polarity",
            )


class TestErrorHandling:
    """Test error handling for common issues."""

    def test_file_not_found(self):
        with pytest.raises(Exception):
            load("nonexistent_file.yaml")

    def test_invalid_yaml_syntax(self):
        from argviz.parser import YAMLParser
        import tempfile

        invalid_yaml = """
nodes:
  - type: Proposition
    id: P1
    content: "unclosed quote
"""
        parser = YAMLParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(invalid_yaml)
            f.flush()
            with pytest.raises(Exception):
                parser.parse(f.name)


class TestEdgeCases:
    """Test edge cases and minimal graphs."""

    def test_minimal_graph_one_node(self):
        from argviz.parser import YAMLParser
        from argviz.model import GraphModel
        import tempfile

        minimal_yaml = """
nodes:
  - type: Conclusion
    id: C1
    content: "Single conclusion"
"""
        parser = YAMLParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(minimal_yaml)
            f.flush()
            model = parser.parse(f.name)
            assert len(model.nodes) == 1
            assert len(model.links) == 0

    def test_graph_with_no_links(self):
        from argviz.parser import YAMLParser
        import tempfile

        no_links_yaml = """
nodes:
  - type: Proposition
    id: P1
    content: "First claim"
  - type: Proposition
    id: P2
    content: "Second claim"
"""
        parser = YAMLParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(no_links_yaml)
            f.flush()
            model = parser.parse(f.name)
            assert len(model.nodes) == 2
            assert len(model.links) == 0

    def test_export_minimal_graph(self):
        from argviz.parser import YAMLParser
        from argviz.exporters.dot import DOTExporter
        import tempfile

        minimal_yaml = """
nodes:
  - type: Conclusion
    id: C1
    content: "Single conclusion"
"""
        parser = YAMLParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(minimal_yaml)
            f.flush()
            model = parser.parse(f.name)
            exporter = DOTExporter()
            dot_output = exporter.export(model)
            assert "digraph" in dot_output
            assert "C1" in dot_output
