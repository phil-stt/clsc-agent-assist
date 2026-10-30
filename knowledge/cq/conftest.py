import pytest

from knowledge import graph

CLIENT = "client:reyes-design-build"
CONTRACT = "contract:larchmont-msa"


@pytest.fixture(scope="session")
def g_seed():
    """The graph as the AMS knows it before the call."""
    return graph.build()


@pytest.fixture(scope="session")
def g():
    """The graph after the call's observations (beats 6 and 7) are written in."""
    g = graph.build()
    graph.observe_location(g, CLIENT, "vernon-yard", "Yard, Vernon", since="2026-09")
    graph.observe_fact(g, CLIENT, "design_work", True,
                       "Design work now done in-house.", as_of="2026-10-29")
    return g


def assert_path(answer, *must_touch):
    """No path, no pass. Every node and edge named must exist in the graph."""
    assert answer.path, f"{answer.question}: no path"
    assert answer.path.nodes and answer.path.edges
    for n in must_touch:
        assert n in answer.path.nodes or n in answer.path.edges, f"path misses {n}"
