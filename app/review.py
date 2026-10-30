"""The review screen's model: the extraction queue, with each proposal's decision.

Reads knowledge/proposed_edges.json (written by `make extract`) and
knowledge/approvals.json (the decisions). A decision is the reviewer's click; it
is appended to the record and the graph is rebuilt, so the call's "show path"
sees the approved edge and its provenance at once.
"""

from __future__ import annotations

import json
from collections import Counter

from knowledge import approvals, extract
from knowledge import graph as kg
from knowledge import queries as q

# The demo's reviewer. A real deployment takes this from the signed-in user.
REVIEWER = "Renee Okafor, compliance lead (fictional)"


def proposals() -> list[dict]:
    if not extract.OUT.exists():
        extract.run(allow_live=False)
    return json.loads(extract.OUT.read_text())["proposals"]


def find(pid: str) -> dict | None:
    return next((p for p in proposals() if p["id"] == pid), None)


def edge_label(g, eid: str | None) -> str | None:
    if not eid:
        return None
    _, etype, ends = eid.split(":", 2)
    src, dst = ends.split(">")
    return f"{q.label(g, src)} {etype} {q.label(g, dst)}"


def view(doc_filter: str = "") -> dict:
    """The queue grouped by document; counts cover the whole queue, the list honors the filter."""
    g = kg.build(reviewed=False)
    done = approvals.decided()
    groups: dict[str, list[dict]] = {}
    counts = Counter()
    for p in proposals():
        d = done.get(p["id"])
        auto = bool(d and d["via"] == approvals.AUTO)
        if not d:
            status, tone = "pending", "amber" if p["match"]["kind"] == "overlaps" else "blue"
        else:
            status = {"approve": "approved", "reject": "rejected", "merge": "merged"}[d["action"]]
            tone = "amber" if status == "rejected" else "green"
        counts["total"] += 1
        counts["waited"] += p["requires_approval"]
        counts["auto"] += auto
        counts["by_person"] += bool(d) and not auto
        counts["pending"] += not d
        if doc_filter and doc_filter not in p["doc"]:
            continue
        groups.setdefault(p["doc"], []).append({
            **p, "status": status, "tone": tone, "decision": d, "auto": auto,
            "from_label": q.label(g, p["from"]), "to_label": q.label(g, p["to"]),
            "match_label": edge_label(g, p["match"]["edge"]),
            "merged_label": edge_label(g, d["merged_into"]) if d and d.get("merged_into") else None})
    log = [{**r, "label": edge_label(g, kg.edge_id(r["type"], r["from"], r["to"]))}
           for r in reversed(approvals.records())]
    return {"groups": groups, "counts": counts, "log": log, "reviewer": REVIEWER, "doc_filter": doc_filter}


def decide(pid: str, action: str) -> dict:
    """The reviewer's click. Merge keeps the curated edge the proposal restates."""
    p = find(pid)
    if p is None:
        raise approvals.ApprovalError(f"no proposal {pid}")
    if action == "merge" and p["match"]["kind"] != "overlaps":
        raise approvals.ApprovalError(f"{pid} doesn't restate an existing edge; approve or reject it")
    rec = approvals.append(p, action, reviewer=REVIEWER, via=approvals.REVIEW_SCREEN,
                           merged_into=p["match"]["edge"] if action == "merge" else None)
    kg.dump(kg.build())
    return rec
