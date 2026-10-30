"""The review record: every decision on a proposed edge, append-only.

extract.py proposes edges; a person decides each one on the review screen
(/review). Each decision is appended to approvals.json and never rewritten.
`make graph` builds the curated seed and then applies this file, so a fresh
clone with the file reproduces the reviewed graph.

The rule this module enforces: an edge type the schema marks
`requires_approval` enters the graph only through a reviewer's decision on the
review screen. Plain data edges may be auto-approved, and say so.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from knowledge import graph as kg

ROOT = Path(__file__).resolve().parent
REVIEW_SCREEN = "review screen"
AUTO = "auto (plain data)"
ACTIONS = ("approve", "reject", "merge")


class ApprovalError(ValueError):
    pass


def path() -> Path:
    return Path(os.environ.get("CLSC_APPROVALS", ROOT / "approvals.json"))


def records() -> list[dict]:
    p = path()
    return json.loads(p.read_text()) if p.exists() else []


def decided() -> dict[str, dict]:
    """The decision on each proposal, by proposal id."""
    return {r["proposal"]: r for r in records()}


def append(proposal: dict, action: str, reviewer: str, via: str, merged_into: str | None = None) -> dict:
    """Record one decision. One decision per proposal; nothing already written changes."""
    if action not in ACTIONS:
        raise ApprovalError(f"unknown action {action!r}")
    recs = records()
    if any(r["proposal"] == proposal["id"] for r in recs):
        raise ApprovalError(f"{proposal['id']} is already decided")
    rec = {"seq": len(recs) + 1, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "proposal": proposal["id"], "action": action,
           "type": proposal["type"], "from": proposal["from"], "to": proposal["to"],
           "condition": proposal.get("condition", ""), "doc": proposal["doc"], "evidence": proposal["evidence"],
           "reviewer": reviewer, "via": via, "merged_into": merged_into}
    check(rec)
    path().write_text(json.dumps(recs + [rec], indent=2, ensure_ascii=False) + "\n")
    return rec


def check(rec: dict) -> None:
    """The gate: a compliance-bearing edge needs a named reviewer on the review screen."""
    spec = kg.load_schema()["edges"].get(rec["type"])
    if spec is None:
        raise ApprovalError(f"{rec['proposal']}: unknown edge type {rec['type']!r}")
    if rec["action"] == "reject":
        return
    if spec["requires_approval"] and (rec["via"] != REVIEW_SCREEN or rec["reviewer"] in ("", "auto")):
        raise ApprovalError(f"{rec['proposal']}: {rec['type']} requires a reviewer's decision on the review screen")
    if rec["action"] == "merge" and not rec.get("merged_into"):
        raise ApprovalError(f"{rec['proposal']}: a merge names the edge it merges into")


def provenance(rec: dict) -> dict:
    return {"proposal": rec["proposal"], "action": rec["action"], "doc": rec["doc"], "quote": rec["evidence"],
            "approver": rec["reviewer"], "via": rec["via"], "at": rec["at"],
            "edge": kg.edge_id(rec["type"], rec["from"], rec["to"])}


def apply(g: nx.MultiDiGraph, recs: list[dict] | None = None) -> nx.MultiDiGraph:
    """Apply decisions on top of the curated graph. Approve adds the edge (or corroborates a curated one);
    merge attaches the proposal's evidence to the edge it restates; reject adds nothing."""
    for rec in records() if recs is None else recs:
        check(rec)
        if rec["action"] == "reject":
            continue
        if rec["action"] == "approve":
            eid = kg.edge_id(rec["type"], rec["from"], rec["to"])
            if not g.has_edge(rec["from"], rec["to"], key=eid):
                edge = {"type": rec["type"], "from": rec["from"], "to": rec["to"], "source": "approved"}
                if rec.get("condition"):
                    edge["condition"] = rec["condition"]
                kg.add_edge(g, edge)
        else:
            eid = rec["merged_into"]
        src, dst = eid.split(":", 2)[2].split(">")
        if not g.has_edge(src, dst, key=eid):
            raise ApprovalError(f"{rec['proposal']}: {eid} is not in the graph")
        g.edges[src, dst, eid].setdefault("provenance", []).append(provenance(rec))
    return g
