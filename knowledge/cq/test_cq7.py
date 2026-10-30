"""CQ7: Can a certificate be issued today showing completed-ops AI?"""
from knowledge.queries import cq7_certificate

from .conftest import CLIENT, CONTRACT, assert_path


def test_cq7_certificate_refused_route_to_endorsement(g):
    a = cq7_certificate(g, CLIENT, CONTRACT)
    assert a.answer["can_issue"] is False
    assert a.answer["human_only"] is True
    assert "req:ai-completed" in a.answer["gaps"]
    assert a.answer["endorsement_forms"] == ["form:CG2037", "form:CG2001"]
    assert "§384" in a.answer["citation"]
    assert_path(a, "rule:certificate-representation",
                "e:APPLIES_IN:rule:certificate-representation>state:CA",
                "e:SATISFIES:form:CG2037>req:ai-completed")
