"""CQ2: Which contract requirements does the policy answer, and which not?"""
from knowledge.queries import cq2_contract_requirements

from .conftest import CLIENT, CONTRACT, assert_path


def test_cq2_requirements(g):
    a = cq2_contract_requirements(g, CLIENT, CONTRACT)
    status = {r["requirement"]: r for r in a.answer["requirements"]}
    assert status["req:ai-ongoing"]["status"] == "satisfied"
    assert status["req:ai-ongoing"]["form"] == "form:CG2033"
    assert status["req:waiver-subrogation"]["status"] == "if_scheduled"
    assert status["req:waiver-subrogation"]["form"] == "form:CG2404"
    assert status["req:ai-completed"]["status"] == "unanswered"
    assert status["req:primary-noncontributory"]["status"] == "unanswered"
    assert status["req:primary-noncontributory"]["remedy_forms"] == ["form:CG2001"]
    assert sorted(a.answer["gaps"]) == ["req:ai-completed", "req:primary-noncontributory"]
    assert_path(a, CONTRACT, "e:REQUIRES:contract:larchmont-msa>req:ai-ongoing",
                "e:SATISFIES:form:CG2033>req:ai-ongoing",
                "e:SATISFIES:form:CG2404>req:waiver-subrogation")
