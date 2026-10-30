"""CQ5: What changed on this account since the underwriting file was written?"""
from knowledge.queries import cq5_changes_since_underwriting

from .conftest import CLIENT, assert_path


def test_cq5_design_work_and_vernon(g):
    a = cq5_changes_since_underwriting(g, CLIENT)
    topics = {c["topic"]: c for c in a.answer["changes"]}
    assert set(topics) == {"design_work", "locations"}
    assert topics["design_work"]["was"].startswith("No design work")
    assert topics["design_work"]["was_as_of"] == "2024-08-14"
    assert "Vernon" in topics["locations"]["now"]
    assert_path(a, "uf:reyes-design-work", "uf:reyes-design-build-design_work-call",
                "e:OPERATES_AT:client:reyes-design-build>location:vernon-yard")
