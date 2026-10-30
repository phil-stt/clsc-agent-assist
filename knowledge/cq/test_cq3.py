"""CQ3: Which disclosures does Contractors Professional Liability trigger here?"""
from knowledge.queries import cq3_disclosures

from .conftest import CLIENT, assert_path


def test_cq3_d1_and_broker_fee_no_exemption(g):
    a = cq3_disclosures(g, CLIENT, "product:cpl")
    assert a.answer["markets"] == ["market:ca-non-admitted"]
    by_id = {d["disclosure"]: d for d in a.answer["disclosures"]}
    assert set(by_id) == {"disclosure:ca-d1", "disclosure:ca-broker-fee"}
    d1 = by_id["disclosure:ca-d1"]
    assert d1["citation"] == "Cal. Ins. Code §1764.1"
    assert d1["signature_required"] is True
    assert d1["exemption"]["applies"] is False
    assert "18 employees, threshold 25" in d1["exemption"]["reason"]
    assert_path(a, "e:PLACED_IN:product:cpl>market:ca-non-admitted",
                "e:TRIGGERS:market:ca-non-admitted>disclosure:ca-d1",
                "e:EXEMPT_WHEN:disclosure:ca-d1>rule:ca-industrial-insured")


def test_cq3_exemption_flips_for_an_industrial_insured(g):
    """Same walk, bigger client: the rule node does the work, not the code."""
    h = g.copy()
    h.nodes[CLIENT]["employees"] = 40
    a = cq3_disclosures(h, CLIENT, "product:cpl", annual_premium=60000)
    d1 = next(d for d in a.answer["disclosures"] if d["disclosure"] == "disclosure:ca-d1")
    assert d1["exemption"]["applies"] is True
    assert d1["signature_required"] is False


def test_cq3_admitted_product_triggers_nothing(g):
    a = cq3_disclosures(g, CLIENT, "product:umbrella")
    assert a.answer["disclosures"] == []
    assert_path(a, "e:PLACED_IN:product:umbrella>market:ca-admitted")
