"""The UI's compliance guarantees: verbatim disclosures and no certificate past a gap."""
import html
import re

import pytest
from fastapi.testclient import TestClient

from knowledge import graph as kg

HX = {"HX-Request": "true"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLSC_DB", str(tmp_path / "state.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # tests replay the cache; they never spend
    from app.main import app
    c = TestClient(app)
    c.post("/restart", headers=HX)
    return c


def verbatim(page: str, disclosure_id: str) -> str:
    m = re.search(rf'<div class="verbatim" data-disclosure="{re.escape(disclosure_id)}">(.*?)</div>', page, re.S)
    assert m, f"{disclosure_id} not on screen"
    return html.unescape(m.group(1))


def test_recorded_line_is_byte_identical_to_file(client):
    page = client.post("/next", headers=HX).text
    on_file = kg.read_disclosure(kg.build(), "disclosure:ca-recorded-line")
    assert verbatim(page, "disclosure:ca-recorded-line") == on_file["text"]
    assert on_file["citation"] in html.unescape(page)
    raw = (kg.DISCLOSURE_DIR / "ca-recorded-line.md").read_text()
    assert raw.split("---\n", 2)[2].strip("\n") == on_file["text"]


def test_skipping_recorded_line_raises_amber_nudge(client):
    client.post("/next", headers=HX)
    page = client.post("/next", headers=HX).text
    assert 'id="card-recorded-line-nudge"' in page
    client.post("/mark/recorded_line", headers=HX)
    page = client.get("/stage", headers=HX).text
    assert 'id="card-recorded-line-nudge"' not in page
    assert "Delivered. Marked by the agent." in page


def test_certificate_cannot_be_issued_with_completed_ops_gap(client):
    client.post("/jump/5", headers=HX)
    page = client.post("/certificate/issue", headers=HX).text
    assert "Certificate refused" in page
    assert "CG 20 37" in page
    assert "Certificate issued" not in page
    # Endorsing doesn't unlock it: the form isn't on the policy until the carrier adds it.
    client.post("/endorsement/start", headers=HX)
    page = client.post("/certificate/issue", headers=HX).text
    assert "Certificate refused" in page


def test_forms_match_shows_the_gap_with_a_path(client):
    page = client.post("/jump/4", headers=HX).text
    assert page.count("Not on the policy") == 2
    assert "Show path" in page


def all_verbatim(page: str, disclosure_id: str) -> list[str]:
    found = re.findall(rf'<div class="verbatim" data-disclosure="{re.escape(disclosure_id)}">(.*?)</div>', page, re.S)
    return [html.unescape(t) for t in found]


def test_waiver_scheduling_rides_on_the_endorsement_request(client):
    page = client.post("/jump/5", headers=HX).text
    assert "Start endorsement request (CG 20 37, CG 20 01, CG 24 04 schedule)" in page
    assert "Yes, if scheduled" in page
    page = client.post("/endorsement/start", headers=HX).text
    assert "Schedule Larchmont Property Group on CG 24 04" in page
    assert "Scheduling requested" in page and "Yes, if scheduled" not in page


def test_new_location_is_observed_once(client):
    """The agent restating "add the Vernon yard" at wrap is not a second location."""
    from app import engine, state as st
    page = client.post("/jump/11", headers=HX).text
    assert 'id="card-location"' in page
    locs = [n for n in engine.world(st.load()) if n.startswith("location:")]
    assert locs == ["location:la-office", "location:yard-in-vernon"]


def test_quote_disclosures_are_verbatim_with_the_exemption_check(client):
    page = client.post("/jump/8", headers=HX).text
    g = kg.build()
    for d in ("disclosure:ca-d1", "disclosure:ca-broker-fee"):
        on_file = kg.read_disclosure(g, d)
        assert all_verbatim(page, d) == [on_file["text"]]
        assert on_file["citation"] in html.unescape(page)
    assert "18 employees, threshold 25: exemption does not apply" in page


def test_quote_is_blocked_until_the_d1_is_delivered(client):
    client.post("/jump/8", headers=HX)
    page = client.post("/quote/request", headers=HX).text
    assert "Quote request blocked" in page
    assert 'id="card-d1-skip"' in page
    d1 = kg.read_disclosure(kg.build(), "disclosure:ca-d1")["text"]
    assert all_verbatim(page, "disclosure:ca-d1") == [d1, d1]  # the D-1 card and the block, both verbatim
    assert "Quote requested by the agent" not in page
    client.post("/mark/ca-d1", headers=HX)
    page = client.post("/quote/request", headers=HX).text
    assert 'id="card-d1-skip"' not in page
    assert "Quote requested by the agent" in page


def test_client_agreeing_to_quote_without_d1_raises_the_block(client):
    page = client.post("/jump/9", headers=HX).text
    assert 'id="card-d1-skip"' in page
    page = client.post("/next", headers=HX).text  # she declines; nothing went out, so nothing was skipped
    assert 'id="card-d1-skip"' not in page
    assert "No application went out" in page


def test_dismissed_recommendation_surfaces_no_disclosures(client):
    client.post("/jump/7", headers=HX)
    client.post("/product/dismissed", headers=HX)
    page = client.post("/next", headers=HX).text
    assert 'id="card-ca-d1"' not in page and 'id="card-quote"' not in page
    assert "Dismissed by the agent" in page


def test_wrap_drafts_stay_in_review_until_accepted(client):
    page = client.post("/jump/11", headers=HX).text
    kinds = ("activity-note", "endorsement-request", "follow-up-email")
    for k in kinds:
        assert re.search(rf'class="card tone-blue" id="card-draft-{k}"', page)
    page = client.post("/wrap/endorsement_request/accept", headers=HX,
                       data={"title": "Endorsement request", "body": "Edited by the agent."}).text
    assert re.search(r'class="card tone-green" id="card-draft-endorsement-request"', page)
    assert "Accepted by the agent with edits. Not sent" in page
    assert re.search(r'class="card tone-blue" id="card-draft-follow-up-email"', page)
