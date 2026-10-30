"""The only place the app calls a model.

Claude does two jobs: read each beat of the call for intent, contract
requirements, locations and exposures; and (later) draft the wrap. It never
decides anything compliance-bearing. What it returns is constrained to ids the
knowledge graph already knows, and the graph does the matching.

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
    prompt = _prompt(beat, history)
    path = CACHE_DIR / f"{_key(prompt)}.json"
    if path.exists():
        return {"result": json.loads(path.read_text())["result"], "source": "claude-cached"}
    if allow_live and os.environ.get("ANTHROPIC_API_KEY"):
        result = _call_claude(prompt)
        if result is not None:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"prompt": prompt, "result": result}, indent=2) + "\n")
            return {"result": result, "source": "claude-live"}
    return {"result": beat["scripted"], "source": "scripted"}


def _call_claude(prompt: dict) -> dict | None:
    import anthropic

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": DETECT_SCHEMA}},
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
