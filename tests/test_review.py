"""The review screen: the only door a compliance-bearing edge comes through."""
import json

import pytest
from fastapi.testclient import TestClient

from knowledge import approvals, extract
from knowledge import graph as kg
from knowledge import queries as q

HX = {"HX-Request": "true"}
CLIENT, CONTRACT = "client:reyes-design-build", "contract:larchmont-msa"


@pytest.fixture()
def review(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CLSC_DB", str(tmp_path / "state.db"))
    monkeypatch.setenv("CLSC_APPROVALS", str(tmp_path / "approvals.json"))
    monkeypatch.setattr(kg, "GRAPH_JSON", tmp_path / "graph.json")
    monkeypatch.setattr(extract, "OUT", tmp_path / "proposed_edges.json")
    from app import engine, review
    engine.base_graph.cache_clear()
    yield review
    engine.base_graph.cache_clear()


def proposal(review, etype, src, dst, doc=None):
    return next(p for p in review.proposals()
                if (p["type"], p["from"], p["to"]) == (etype, src, dst) and (doc is None or p["doc"].endswith(doc)))


def test_rejected_proposal_never_appears_in_the_graph(review):
    p = proposal(review, "MANDATES", "state:CA", "disclosure:ca-broker-fee")
    review.decide(p["id"], "reject")
    g = kg.build()
    assert not g.has_edge("state:CA", "disclosure:ca-broker-fee")
    a = q.cq3_disclosures(g, CLIENT, "product:cpl")
    assert p["edge_id"] not in a.path.edges
    assert not any(pv["proposal"] == p["id"] for *_, d in g.edges(data=True) for pv in d.get("provenance", []))


def test_approved_proposal_carries_provenance_into_the_cq_path(review):
    p = proposal(review, "SATISFIES", "form:CG2037", "req:ai-completed", doc="cg-20-37.md")
    review.decide(p["id"], "approve")
    g = kg.build()
    a = q.cq1_completed_ops(g, CLIENT)
    prov = q.provenance(g, a.path)
    assert [(x["edge"], x["doc"], x["quote"], x["approver"]) for x in prov] == [
        (p["edge_id"], p["doc"], p["evidence"], review.REVIEWER)]
    # And on screen: the call's "show path" carries the same line.
    from app.main import app
    c = TestClient(app)
    page = c.post("/jump/4", headers=HX).text
    assert f'data-provenance="{p["id"]}"' in page and review.REVIEWER in page
    # A new edge enters the graph the same way, with its provenance.
    n = proposal(review, "MANDATES", "state:CA", "disclosure:ca-d1")
    review.decide(n["id"], "approve")
    d = kg.build().edges["state:CA", "disclosure:ca-d1", n["edge_id"]]
    assert d["source"] == "approved" and d["provenance"][0]["doc"] == n["doc"]


def test_merging_mandates_into_triggers_leaves_one_edge_of_that_meaning(review):
    for disc in ("disclosure:ca-d1", "disclosure:ca-broker-fee"):
        p = proposal(review, "MANDATES", "state:CA", disc)
        assert p["match"]["kind"] == "overlaps"
        review.decide(p["id"], "merge")
        g = kg.build()
        into = [d for _, _, d in g.in_edges(disc, data=True)]
        assert [d["type"] for d in into] == ["TRIGGERS"]
        assert into[0]["provenance"][0]["proposal"] == p["id"]
        with pytest.raises(approvals.ApprovalError):  # decided once; the record doesn't change
            review.decide(p["id"], "approve")
    # The call still finds both disclosures through the edge that stayed.
    names = [r["name"] for r in q.cq3_disclosures(kg.build(), CLIENT, "product:cpl").answer["disclosures"]]
    assert len(names) == 2


def test_compliance_edges_have_no_route_in_but_the_review_screen(review, tmp_path):
    review.proposals()  # extraction runs, auto-approving what it may
    auto = approvals.records()
    assert auto and all(not kg.load_schema()["edges"][r["type"]]["requires_approval"] for r in auto)
    p = proposal(review, "SATISFIES", "form:CG2001", "req:primary-noncontributory")
    for via, reviewer in ((approvals.AUTO, "auto"), ("extract", "auto"), (approvals.REVIEW_SCREEN, "")):
        with pytest.raises(approvals.ApprovalError):
            approvals.append(p, "approve", reviewer=reviewer, via=via)
    # A record written around the screen is refused when the graph builds.
    forged = {**auto[0], "seq": 99, "proposal": p["id"], "type": p["type"], "from": p["from"], "to": p["to"]}
    approvals.path().write_text(json.dumps(auto + [forged]))
    with pytest.raises(approvals.ApprovalError):
        kg.build()


def test_review_screen_lists_the_queue_and_records_each_click(review):
    from app.main import app
    c = TestClient(app)
    page = c.get("/review").text
    assert page.count('class="prop ') == 32
    assert "Waited for a person" in page and "Merge into TRIGGERS" in page
    assert "<dt>Proposals</dt><dd>32</dd>" in page and "<dt>Waited for a person</dt><dd>28</dd>" in page
    p = proposal(review, "PLACED_IN", "product:umbrella", "market:ca-admitted")
    page = c.post(f"/review/{p['id']}/reject", headers=HX).text
    assert "Rejected; never enters the graph." in page
    rec = approvals.decided()[p["id"]]
    assert (rec["action"], rec["reviewer"], rec["via"]) == ("reject", review.REVIEWER, approvals.REVIEW_SCREEN)
