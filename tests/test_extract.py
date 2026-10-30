"""Extraction replays from the recorded responses and produces a checked review queue."""
import json

from knowledge import extract


def test_extract_writes_a_checked_non_empty_queue(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(extract, "OUT", tmp_path / "proposed_edges.json")
    out = extract.run(allow_live=False)
    assert out["responses"] == {"claude-cached": out["documents"]}
    props = json.loads((tmp_path / "proposed_edges.json").read_text())["proposals"]
    assert props and all(p["status"] == "proposed" for p in props)
    assert all(p["schema_ok"] and p["evidence_found"] for p in props)
    assert any(p["in_curated_graph"] for p in props) and any(not p["in_curated_graph"] for p in props)
