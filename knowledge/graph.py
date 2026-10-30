"""Build the knowledge graph from the curated seed and persist it as JSON.

The graph is a NetworkX MultiDiGraph. Node ids are "<kind>:<slug>"; every edge
carries a stable id ("e:<TYPE>:<from>><to>") so a competency answer can name
exactly which edges it walked.

    python -m knowledge.graph      # validate the seed and write knowledge/graph.json
"""

from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

import networkx as nx
import yaml

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schema.yaml"
SEED_DIR = ROOT / "seed"
DISCLOSURE_DIR = ROOT / "disclosures"
GRAPH_JSON = Path(os.environ.get("CLSC_GRAPH", ROOT / "graph.json"))


class SchemaError(ValueError):
    pass


def edge_id(etype: str, src: str, dst: str) -> str:
    return f"e:{etype}:{src}>{dst}"


@lru_cache(maxsize=1)
def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text())


def add_node(g: nx.MultiDiGraph, node: dict) -> None:
    schema = load_schema()
    node = dict(node)
    nid, ntype = node.pop("id"), node.get("type")
    if ntype not in schema["entities"]:
        raise SchemaError(f"{nid}: unknown entity type {ntype!r}")
    g.add_node(nid, **node)


def add_edge(g: nx.MultiDiGraph, edge: dict) -> str:
    schema = load_schema()
    edge = dict(edge)
    etype, src, dst = edge.pop("type"), edge.pop("from"), edge.pop("to")
    spec = schema["edges"].get(etype)
    if spec is None:
        raise SchemaError(f"unknown edge type {etype!r}")
    for end, want in ((src, spec["from"]), (dst, spec["to"])):
        if end not in g:
            raise SchemaError(f"{etype}: missing node {end}")
        if g.nodes[end]["type"] != want:
            raise SchemaError(f"{etype}: {end} is {g.nodes[end]['type']}, schema wants {want}")
    eid = edge_id(etype, src, dst)
    g.add_edge(src, dst, key=eid, id=eid, type=etype,
               requires_approval=spec["requires_approval"], **edge)
    return eid


def build(reviewed: bool = True) -> nx.MultiDiGraph:
    """The curated seed, then (unless reviewed=False) the decisions in approvals.json."""
    g = nx.MultiDiGraph()
    docs = [yaml.safe_load(p.read_text()) for p in sorted(SEED_DIR.glob("*.yaml"))]
    for doc in docs:
        for node in doc.get("nodes", []):
            add_node(g, node)
    for doc in docs:
        for edge in doc.get("edges", []):
            add_edge(g, edge)
    if reviewed:
        from knowledge import approvals
        approvals.apply(g)
    return g


# --- Observations from the call -------------------------------------------
# Facts the agent learns live are written into the graph the same way the AMS
# data is, tagged with their source, so the competency questions see them.

def observe_location(g: nx.MultiDiGraph, client: str, slug: str, name: str,
                     since: str, source: str = "call") -> str:
    nid = f"location:{slug}"
    if nid not in g:
        add_node(g, {"id": nid, "type": "Location", "name": name,
                     "since": since, "source": source, "synthetic": True})
        add_edge(g, {"type": "OPERATES_AT", "from": client, "to": nid, "source": source})
    return nid


def observe_fact(g: nx.MultiDiGraph, client: str, topic: str, value, text: str,
                 as_of: str | None = None, source: str = "call") -> str:
    as_of = as_of or date.today().isoformat()
    nid = f"uf:{client.split(':', 1)[1]}-{topic}-{source}"
    if nid not in g:
        add_node(g, {"id": nid, "type": "UnderwritingFact", "topic": topic, "value": value,
                     "text": text, "as_of": as_of, "source": source})
        add_edge(g, {"type": "ABOUT", "from": nid, "to": client})
    return nid


def read_disclosure(g: nx.MultiDiGraph, disclosure_id: str) -> dict:
    """The verbatim disclosure, split from its metadata header. Read-only by design."""
    raw = (DISCLOSURE_DIR / g.nodes[disclosure_id]["file"]).read_text()
    _, header, body = raw.split("---\n", 2)
    meta = yaml.safe_load(header)
    return {"id": disclosure_id, "text": body.strip("\n"), **meta}


def dump(g: nx.MultiDiGraph, path: Path = GRAPH_JSON) -> None:
    data = nx.node_link_data(g, edges="edges")
    path.write_text(json.dumps(data, indent=2, default=str))


def load(path: Path = GRAPH_JSON) -> nx.MultiDiGraph:
    return nx.node_link_graph(json.loads(path.read_text()), directed=True,
                              multigraph=True, edges="edges")


if __name__ == "__main__":
    graph = build()
    dump(graph)
    gated = sum(1 for *_, d in graph.edges(data=True) if d["requires_approval"])
    reviewed = sum(1 for *_, d in graph.edges(data=True) if d.get("provenance"))
    print(f"graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges "
          f"({gated} compliance-bearing, {reviewed} with review provenance) -> {GRAPH_JSON}")
