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
