"""Approach C's extraction half: Claude reads the corpus and proposes edges.

Each document in knowledge/docs/ goes to Claude with the edge types it may
propose and the catalog of library nodes. Every proposal is checked against the
schema and its evidence quote against the document, compared with the curated
graph, and written to proposed_edges.json as a review queue. Nothing here
changes the graph: a compliance-bearing edge enters only when a person approves
it on the review screen (/review). Proposals on plain data edges are
auto-approved into knowledge/approvals.json, tagged as such.

    python -m knowledge.extract    # replays recorded responses; calls Claude only for new prompts
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app import llm
from knowledge import approvals
from knowledge import graph as kg

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
OUT = ROOT / "proposed_edges.json"

# Library relationships, the ones a document can state. Client data (HAS, ATTACHES,
# COVERS, ...) comes from the agency management system, not from reading forms.
EXTRACTABLE = ["SATISFIES", "PLACED_IN", "TRIGGERS", "EXEMPT_WHEN", "ADDRESSED_BY",
               "APPLIES_IN", "MANDATES", "OFFERED_BY"]


def catalog(g) -> list[dict]:
    schema = kg.load_schema()["edges"]
    kinds = {schema[t][end] for t in EXTRACTABLE for end in ("from", "to")}
    return [{"id": n, "type": d["type"], "name": d.get("number") or d.get("name") or n}
            for n, d in sorted(g.nodes(data=True)) if d["type"] in kinds]


def proposal_id(doc: str, e: dict) -> str:
    return "p-" + hashlib.sha256(f"{doc}|{e['type']}|{e['from']}|{e['to']}".encode()).hexdigest()[:8]


def match(g, e: dict) -> dict:
    """Matches a curated edge, overlaps one (another relation already reaches the same node), or is new."""
    eid = kg.edge_id(e["type"], e["from"], e["to"])
    if g.has_edge(e["from"], e["to"], key=eid):
        return {"kind": "matches", "edge": eid}
    gated = kg.load_schema()["edges"][e["type"]]["requires_approval"]
    for src, _, d in g.in_edges(e["to"], data=True):
        if d["type"] != e["type"] and d["requires_approval"] == gated:
            return {"kind": "overlaps", "edge": d["id"]}
    return {"kind": "new", "edge": None}


def check(g, e: dict, text: str) -> dict:
    """Schema-valid? Evidence really in the document? Already in the curated graph?"""
    probe = g.copy()
    try:
        kg.add_edge(probe, {"type": e["type"], "from": e["from"], "to": e["to"]})
        problem = None
    except kg.SchemaError as err:
        problem = str(err)
    eid = kg.edge_id(e["type"], e["from"], e["to"])
    flat = " ".join(text.split())
    return {"edge_id": eid, "schema_ok": problem is None, "schema_problem": problem,
            "evidence_found": " ".join(e["evidence"].split()) in flat,
            "in_curated_graph": g.has_edge(e["from"], e["to"], key=eid),
            "requires_approval": kg.load_schema()["edges"][e["type"]]["requires_approval"]}


def run(allow_live: bool = True) -> dict:
    g = kg.build(reviewed=False)
    nodes = catalog(g)
    edge_types = {t: kg.load_schema()["edges"][t] for t in EXTRACTABLE}
    proposals, sources = [], Counter()
    docs = sorted(p for p in DOCS.rglob("*.md") if p.name != "README.md")
    for path in docs:
        rel = str(path.relative_to(ROOT))
        text = path.read_text()
        r = llm.propose_edges(rel, text, nodes, edge_types, allow_live=allow_live)
        sources[r["source"]] += 1
        for e in (r["result"] or {}).get("edges", []):
            proposals.append({"id": proposal_id(rel, e), **e, **check(g, e, text), "match": match(g, e),
                              "doc": rel, "status": "proposed"})
    # Plain data edges don't wait for a person; the record says so.
    done = approvals.decided()
    for p in proposals:
        if not p["requires_approval"] and p["schema_ok"] and p["id"] not in done:
            approvals.append(p, "approve", reviewer="auto", via=approvals.AUTO)
    counts = Counter()
    for p in proposals:
        counts["total"] += 1
        counts["matches_curated"] += p["in_curated_graph"]
        counts["new"] += not p["in_curated_graph"]
        counts["needs_approval"] += p["requires_approval"]
        counts["overlaps"] += p["match"]["kind"] == "overlaps"
        counts["schema_rejected"] += not p["schema_ok"]
        counts["evidence_not_found"] += not p["evidence_found"]
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "model": llm.MODEL, "prompt_version": llm.EXTRACT_VERSION,
           "documents": len(docs), "responses": dict(sources), "counts": dict(counts),
           "proposals": proposals}
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    return out


if __name__ == "__main__":
    out = run()
    c = out["counts"]
    print(f"extract: {out['documents']} documents ({', '.join(f'{v} {k}' for k, v in out['responses'].items())}); "
          f"{c.get('total', 0)} proposals, {c.get('matches_curated', 0)} match the curated graph, "
          f"{c.get('new', 0)} new, {c.get('needs_approval', 0)} need approval, "
          f"{c.get('schema_rejected', 0)} fail the schema -> {OUT.relative_to(ROOT.parent)}")
