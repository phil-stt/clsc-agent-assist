"""CQ4: Which locations does the client operate at that the policy doesn't cover?"""
from knowledge.queries import cq4_uncovered_locations

from .conftest import CLIENT, assert_path


def test_cq4_vernon_yard_uncovered(g):
    a = cq4_uncovered_locations(g, CLIENT)
    assert a.answer["uncovered"] == ["location:vernon-yard"]
    assert_path(a, "e:OPERATES_AT:client:reyes-design-build>location:vernon-yard",
                "e:COVERS:policy:gl-wbm-4471902>location:la-office")


def test_cq4_before_the_call_nothing_is_missing(g_seed):
    a = cq4_uncovered_locations(g_seed, CLIENT)
    assert a.answer["uncovered"] == []
