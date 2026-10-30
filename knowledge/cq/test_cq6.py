"""CQ6: Does the GL cover design work done in-house?"""
from knowledge.queries import cq6_exposure

from .conftest import CLIENT, assert_path


def test_cq6_professional_services_excluded(g):
    a = cq6_exposure(g, CLIENT, "exposure:professional-services")
    assert a.answer["covered"] is False
    assert a.answer["excluded_by"] == "CG 22 79"
    assert a.answer["products"] == [{"product": "product:cpl", "name": "Contractors Professional Liability",
                                     "market": "market:ca-non-admitted", "market_kind": "non-admitted"}]
    assert_path(a, "e:EXCLUDES:coverage:gl-reyes>exposure:professional-services",
                "e:ADDRESSED_BY:exposure:professional-services>product:cpl",
                "e:PLACED_IN:product:cpl>market:ca-non-admitted")
