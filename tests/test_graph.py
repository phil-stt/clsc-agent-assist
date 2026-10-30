from knowledge import graph as kg


def test_graph_round_trips_through_json(tmp_path):
    g = kg.build()
    kg.dump(g, tmp_path / "g.json")
    h = kg.load(tmp_path / "g.json")
    assert sorted(g.nodes) == sorted(h.nodes)
    assert sorted(k for *_, k in g.edges(keys=True)) == sorted(k for *_, k in h.edges(keys=True))


def test_compliance_edges_are_flagged_for_approval():
    g = kg.build()
    gated = {d["type"] for *_, d in g.edges(data=True) if d["requires_approval"]}
    assert {"SATISFIES", "PLACED_IN", "TRIGGERS", "EXEMPT_WHEN", "EXCLUDES"} <= gated
    assert not {"HAS", "ATTACHES", "COVERS"} & gated


def test_seed_has_no_empty_attributes():
    """A bare comma inside a YAML flow mapping splits a value into stray null keys."""
    g = kg.build()
    assert not [(n, k) for n, d in g.nodes(data=True) for k, v in d.items() if v is None]
    assert not [(d["id"], k) for *_, d in g.edges(data=True) for k, v in d.items() if v is None]
