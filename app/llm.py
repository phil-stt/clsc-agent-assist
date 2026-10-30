"""The only place the project calls a model.

Claude does three jobs: read each beat of the call for intent, contract
requirements, locations and exposures; draft the after-call wrap from facts the
graph already settled; and, offline, propose graph edges from the document
corpus (knowledge/extract.py). It never decides anything compliance-bearing.
What it returns is constrained to ids the knowledge graph already knows, and the
graph does the matching.

Responses are cached on disk by prompt hash. The transcript is scripted, so the
cache makes the demo deterministic and free to replay. With no cache entry and
no API key, the beat's scripted detection is used and labeled as such.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "llm_cache"
MODEL = "claude-opus-5-5"
PROMPT_VERSION = "detect-v1"

load_dotenv(ROOT / ".env")

REQUIREMENTS = ["req:ai-ongoing", "req:ai-completed", "req:primary-noncontributory", "req:waiver-subrogation"]
EXPOSURES = ["exposure:professional-services", "exposure:cyber", "exposure:non-owned-auto"]
INTENTS = ["greeting", "identify", "certificate_request", "forms_review", "client_pressure",
           "location_change", "operations_change", "quote_request", "decline", "wrap", "other"]

DETECT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "call_type": {"type": "string", "enum": ["certificate_request", "endorsement", "billing", "renewal", "none"]},
        "requirements": {"type": "array", "items": {"type": "string", "enum": REQUIREMENTS}},
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "when": {"type": "string"}},
                "required": ["name", "when"],
                "additionalProperties": False,
            },
        },
        "exposures": {"type": "array", "items": {"type": "string", "enum": EXPOSURES}},
        "evidence": {"type": "string"},
    },
    "required": ["intent", "call_type", "requirements", "locations", "exposures", "evidence"],
    "additionalProperties": False,
}

DETECT_SYSTEM = """You follow a live phone call between a commercial lines account manager at an insurance agency and a business client, one utterance at a time. For the latest utterance, report what it signals. Only report what the utterance itself says; use the earlier lines for context only.

- intent: what the latest line is doing in the call.
- call_type: the kind of service call this is, once it is clear; "none" before then.
- requirements: contract insurance requirements the speaker states, as ids. req:ai-ongoing = additional insured for ongoing operations; req:ai-completed = additional insured for completed operations; req:primary-noncontributory = primary and noncontributory; req:waiver-subrogation = waiver of subrogation.
- locations: business premises the client mentions that are new or changed, with when they started.
- exposures: loss exposures the line reveals, as ids. exposure:professional-services = design, engineering, drawings or specifications the business performs; exposure:cyber = data, networks, privacy; exposure:non-owned-auto = employees driving personal or rented vehicles for work.
- evidence: the shortest phrase from the latest line that supports your answer.

You are not deciding coverage, products or disclosures. Report signals only."""


def _key(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]


def _prompt(beat: dict, history: list[dict]) -> dict:
    lines = [f"[{b['t']}] {b['speaker'].upper()}: {b['text']}" for b in history[-3:]]
    latest = f"[{beat['t']}] {beat['speaker'].upper()}: {beat['text']}"
    context = "\n".join(lines) or "(start of call)"
    return {"model": MODEL, "version": PROMPT_VERSION, "system": DETECT_SYSTEM,
            "user": f"Earlier in the call:\n{context}\n\nLatest utterance:\n{latest}"}


def detect(beat: dict, history: list[dict], allow_live: bool = True) -> dict:
    """Signals for one beat: {'result': {...}, 'source': 'claude-cached' | 'claude-live' | 'scripted'}."""
    result, source = cached_call(_prompt(beat, history), DETECT_SCHEMA, allow_live)
    if result is None:
        return {"result": beat["scripted"], "source": "scripted"}
    return {"result": result, "source": source}


# --- The wrap ----------------------------------------------------------------

WRAP_VERSION = "wrap-v1"

_DRAFT = {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
          "required": ["title", "body"], "additionalProperties": False}
WRAP_SCHEMA = {
    "type": "object",
    "properties": {"activity_note": _DRAFT, "endorsement_request": _DRAFT, "follow_up_email": _DRAFT},
    "required": ["activity_note", "endorsement_request", "follow_up_email"],
    "additionalProperties": False,
}

WRAP_SYSTEM = """You draft the after-call work for a commercial lines account manager at an insurance agency. You get the facts of the call as JSON. Every fact you need is there; use only those facts.

Write three drafts:
- activity_note: the note for the agency management system. Plain, factual, past tense, short lines. What the client asked, what was found, what the agent did and decided, what is open, the follow-up date.
- endorsement_request: to the carrier's underwriter, asking for each policy change in the facts, with the policy number and the reason (the contract requirement or the new location). One request, itemized.
- follow_up_email: to the client, from the agent, first names. Warm and brief. What happens next on the certificate, what was noted about the new location, and the professional liability information she asked for in writing, with the follow-up date.

Rules. These are regulated documents and a licensed agent will review them before anything is sent.
- Never say or imply that anything is covered, bound, or approved. Endorsements are requested, not in force. A certificate goes out only after the carrier confirms the endorsements.
- Never promise a date the facts don't give.
- Never quote, paraphrase or summarize disclosure text. Refer to a disclosure only by its name, and only to say when it is delivered or signed.
- No premium figures, no coverage advice, no legal advice.
- Sign the email with the agent's first name and the agency name. No placeholders in brackets."""


def draft_wrap(facts: dict, allow_live: bool = True) -> dict:
    """The three wrap drafts: {'result': {...} | None, 'source': ...}. None means no model and no cache."""
    prompt = {"model": MODEL, "version": WRAP_VERSION, "system": WRAP_SYSTEM,
              "user": json.dumps(facts, indent=2, sort_keys=True)}
    result, source = cached_call(prompt, WRAP_SCHEMA, allow_live)
    return {"result": result, "source": source}


# --- Edge extraction (offline; knowledge/extract.py) -------------------------------

EXTRACT_VERSION = "extract-v1"

EXTRACT_SYSTEM = """You read one document from an insurance agency's knowledge corpus (a policy form summary, a product sheet, or a statute excerpt) and propose relationships for the agency's knowledge graph.

You get the edge types you may propose, each with the node types it connects, and the catalog of nodes that already exist. Propose an edge only when this document states the relationship. Use only node ids from the catalog. Don't propose edges the document merely makes plausible.

For each edge give:
- condition: the condition the document attaches to it, in a short phrase, or "" if none.
- evidence: a short exact quote from the document that states it.

A person reviews every proposal before it enters the graph. Fewer, well-evidenced edges beat many guesses. Return an empty list if the document states none."""


def propose_edges(doc: str, text: str, nodes: list[dict], edge_types: dict, allow_live: bool = True) -> dict:
    """Proposed edges for one corpus document: {'result': {'edges': [...]} | None, 'source': ...}."""
    schema = {
        "type": "object",
        "properties": {"edges": {"type": "array", "items": {
            "type": "object",
            "properties": {"type": {"type": "string", "enum": sorted(edge_types)},
                           "from": {"type": "string", "enum": [n["id"] for n in nodes]},
                           "to": {"type": "string", "enum": [n["id"] for n in nodes]},
                           "condition": {"type": "string"},
                           "evidence": {"type": "string"}},
            "required": ["type", "from", "to", "condition", "evidence"],
            "additionalProperties": False}}},
        "required": ["edges"],
        "additionalProperties": False,
    }
    types = "\n".join(f"- {t}: {s['from']} -> {s['to']}" for t, s in sorted(edge_types.items()))
    catalog = "\n".join(f"- {n['id']} ({n['type']}): {n['name']}" for n in nodes)
    prompt = {"model": MODEL, "version": EXTRACT_VERSION, "system": EXTRACT_SYSTEM,
              "user": f"Edge types:\n{types}\n\nNode catalog:\n{catalog}\n\nDocument ({doc}):\n\n{text}"}
    result, source = cached_call(prompt, schema, allow_live)
    return {"result": result, "source": source}


# --- Calling Claude, through the cache -----------------------------------------

def cached_call(prompt: dict, schema: dict, allow_live: bool = True) -> tuple[dict | None, str]:
    """Replay a recorded response, or make the call and record it. (None, 'none') when neither is possible."""
    path = CACHE_DIR / f"{_key(prompt)}.json"
    if path.exists():
        return json.loads(path.read_text())["result"], "claude-cached"
    if allow_live and os.environ.get("ANTHROPIC_API_KEY"):
        result = _call_claude(prompt, schema)
        if result is not None:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"prompt": prompt, "result": result}, indent=2) + "\n")
            return result, "claude-live"
    return None, "none"


def _call_claude(prompt: dict, schema: dict) -> dict | None:
    import anthropic

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
        )
    except anthropic.APIConnectionError:
        return None
    except anthropic.APIStatusError:
        return None
    if response.stop_reason in ("refusal", "max_tokens"):
        return None
    text = next((b.text for b in response.content if b.type == "text"), None)
    return json.loads(text) if text else None
