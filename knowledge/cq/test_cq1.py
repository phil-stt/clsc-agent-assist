"""CQ1: Does the GL give completed-operations AI status to a scheduled party?"""
from knowledge.queries import cq1_completed_ops

from .conftest import CLIENT, assert_path


def test_cq1_completed_ops_not_on_policy(g):
    a = cq1_completed_ops(g, CLIENT)
    assert a.answer["status"] == "unanswered"
    assert a.answer["remedy_forms"] == ["form:CG2037"]
    assert_path(a, CLIENT, "policy:gl-wbm-4471902", "form:CG2033", "req:ai-completed",
                "e:ATTACHES:policy:gl-wbm-4471902>form:CG2033",
                "e:SATISFIES:form:CG2037>req:ai-completed")
    # The walk found CG 20 37 as the remedy, not as an attached form.
    assert "e:ATTACHES:policy:gl-wbm-4471902>form:CG2037" not in a.path.edges
