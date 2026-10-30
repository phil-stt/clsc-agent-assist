"""The co-pilot: turns call state into panel cards.

Per beat, Claude reads the line (app.llm.detect); everything compliance-bearing
(which forms answer which requirement, whether a certificate can issue, which
disclosure applies) is a graph walk in knowledge.queries. Cards carry a tone:
blue is the AI proposing, green is a human decision, amber is a block or nudge.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import networkx as nx
import yaml

from app import llm, state as st
from knowledge import graph as kg
from knowledge import queries as q

ROOT = Path(__file__).resolve().parent.parent
CALL_PATH = ROOT / "data" / "call.yaml"


@lru_cache(maxsize=1)
def call() -> dict:
    return yaml.safe_load(CALL_PATH.read_text())


def beats() -> list[dict]:
    return call()["beats"]


@lru_cache(maxsize=1)
def base_graph() -> nx.MultiDiGraph:
    return kg.load() if kg.GRAPH_JSON.exists() else kg.build()


def client() -> str:
    return call()["call"]["client"]


def contract() -> str:
    return call()["call"]["contract"]


def detection(state: dict, n: int) -> dict | None:
    return state["detections"].get(str(n))


def new_locations(r: dict) -> list[dict]:
    """Locations count as observed only on the beat that reports the change, not when the agent restates it at wrap."""
    return r["locations"] if r["intent"] == "location_change" else []


def world(state: dict) -> nx.MultiDiGraph:
    """The graph as it stands at this point in the call, observations included."""
    g = base_graph().copy()
    for n in range(1, state["beat"] + 1):
        d = detection(state, n)
        if not d:
            continue
        for loc in new_locations(d["result"]):
            slug = re.sub(r"[^a-z0-9]+", "-", loc["name"].lower()).strip("-")
            kg.observe_location(g, client(), slug, loc["name"], since=loc["when"])
        if "exposure:professional-services" in d["result"]["exposures"] and d["result"]["intent"] == "operations_change":
            kg.observe_fact(g, client(), "design_work", True, "Design work now done in-house.")
    return g


# --- Moving the call --------------------------------------------------------

def advance(state: dict) -> dict:
    if state["beat"] >= len(beats()):
        state["playing"] = False
        return state
    if state["beat"] == 1 and "recorded_line" not in state["marks"]:
        st.log(state, "ai", "amber", "nudge",
               "Recorded-line notice not marked delivered. California requires all-party consent.")
    state["beat"] += 1
    beat = beats()[state["beat"] - 1]
    history = beats()[: state["beat"] - 1]
    d = llm.detect(beat, history)
    state["detections"][str(beat["n"])] = d
    _log_beat(state, beat, d)
    return state


def _log_beat(state: dict, beat: dict, d: dict) -> None:
    r, src = d["result"], d["source"]
    who = {"claude-cached": "Claude (cached)", "claude-live": "Claude", "scripted": "Scripted fallback"}[src]
    st.log(state, "system", "plain", "transcript", f"{beat['speaker'].title()}: {beat['text']}")
    if r["intent"] == "certificate_request":
        names = ", ".join(base_graph().nodes[x]["name"] for x in r["requirements"])
        st.log(state, "ai", "blue", "detect", f"{who}: certificate request. Requirements parsed: {names}.", source=src)
    if beat["n"] == 2:
        st.log(state, "ai", "blue", "account", "Account pulled from the AMS record: Reyes Design Build, Inc.")
    if beat["n"] == 4:
        g = world(state)
        a = q.cq2_contract_requirements(g, client(), contract())
        st.log(state, "ai", "blue", "forms", f"Forms read from the GL. {a.summary}.", path=a.path.edges)
    if beat["n"] == 5:
        a = q.certificate_check(world(state), client(), contract())
        if not a.answer["can_issue"]:
            st.log(state, "ai", "amber", "block", "Certificate blocked: " + a.answer["reason"], path=a.path.edges)
    for loc in new_locations(r):
        st.log(state, "ai", "blue", "detect", f"{who}: new location mentioned, {loc['name']} ({loc['when']}).", source=src)
    for exp in r["exposures"]:
        if r["intent"] == "operations_change":
            st.log(state, "ai", "blue", "detect",
                   f"{who}: exposure raised, {base_graph().nodes[exp]['name']}.", source=src)


# --- Human actions ----------------------------------------------------------

def mark(state: dict, what: str) -> dict:
    state["marks"][what] = {"beat": state["beat"]}
    label = {"recorded_line": "Recorded-line notice delivered"}.get(what, what)
    st.log(state, "agent", "green", "mark", f"{label} (marked by agent).")
    return state


def issue_certificate(state: dict) -> tuple[dict, dict]:
    """Human-only, and only when the policy supports every line. Refuses otherwise."""
    a = q.certificate_check(world(state), client(), contract())
    if not a.answer["can_issue"]:
        st.log(state, "agent", "amber", "refused",
               "Issue certificate refused: " + a.answer["reason"], path=a.path.edges)
        return state, {"issued": False, "reason": a.answer["reason"]}
    st.log(state, "agent", "green", "certificate", "Certificate issued by agent.")
    return state, {"issued": True}


def start_endorsement(state: dict) -> dict:
    a = q.certificate_check(world(state), client(), contract())
    forms = [base_graph().nodes[f]["number"] for f in a.answer["endorsement_forms"]]
    state["decisions"]["endorsement"] = {"beat": state["beat"], "forms": forms, "carrier": "Westbrook Mutual"}
    st.log(state, "agent", "green", "decision",
           f"Endorsement request started by agent: {', '.join(forms)} to Westbrook Mutual.")
    return state


# --- The panel ----------------------------------------------------------------

def path_view(g: nx.MultiDiGraph, path: q.Path) -> list[dict]:
    rows = []
    for eid in path.edges:
        _, etype, ends = eid.split(":", 2)
        src, dst = ends.split(">")
        data = next(d for _, _, k, d in g.out_edges(src, keys=True, data=True) if k == eid)
        rows.append({"id": eid, "type": etype, "src": src, "dst": dst,
                     "src_label": q.label(g, src), "dst_label": q.label(g, dst),
                     "gated": data["requires_approval"]})
    return rows


def suggested_words(g: nx.MultiDiGraph, rows: list[dict]) -> str:
    def phrase(r):
        return {"req:ai-ongoing": "additional insured while your crew is working",
                "req:ai-completed": "additional insured after the job is finished (completed operations)",
                "req:primary-noncontributory": "primary and noncontributory",
                "req:waiver-subrogation": "the waiver of subrogation"}[r["requirement"]]
    have = [phrase(r) for r in rows if r["status"] == "satisfied"]
    sched = [phrase(r) for r in rows if r["status"] == "if_scheduled"]
    gaps = [phrase(r) for r in rows if r["status"] == "unanswered"]
    parts = ["Marisol, I have your general liability open and I read what's actually on it."]
    if have:
        parts.append(f"It already gives Larchmont {', '.join(have)}.")
    if sched:
        parts.append(f"It has {', '.join(sched)}; Larchmont just needs to be added to that schedule.")
    if gaps:
        parts.append(f"It does not have {' or '.join(gaps)} yet, and a certificate can only show what the "
                     "policy actually has, so I can't send one today that shows those.")
        parts.append("I'm sending Westbrook the request to add them right now, and I'll get you the "
                     "certificate the moment they confirm. Let me see if I can get that back before Monday.")
    return " ".join(parts)


def panel(state: dict) -> list[dict]:
    g = world(state)
    n = state["beat"]
    cards: list[dict] = []
    if n >= 1:
        disc = kg.read_disclosure(g, "disclosure:ca-recorded-line")
        delivered = "recorded_line" in state["marks"]
        cards.append({"kind": "disclosure", "id": "recorded-line", "beat": 1,
                      "tone": "green" if delivered else "blue",
                      "title": "Recorded-line notice", "disclosure": disc,
                      "mark": "recorded_line", "delivered": delivered,
                      "lede": "Read this verbatim before any account discussion."})
        if n >= 2 and not delivered:
            cards.append({"kind": "nudge", "id": "recorded-line-nudge", "beat": n + 0.5, "tone": "amber",
                          "title": "Recorded-line notice not marked delivered",
                          "body": "The call has moved on. California requires all parties to consent to "
                                  "recording; deliver the notice now and mark it.",
                          "mark": "recorded_line", "citation": disc["citation"]})
    if n >= 2:
        a = q.account_summary(g, client())
        cards.append({"kind": "account", "id": "account", "beat": 2, "tone": "blue",
                      "title": "Account", "a": a.answer, "path": path_view(g, a.path)})
    if n >= 3:
        d = detection(state, 3)
        reqs = [{"id": r, "name": g.nodes[r]["name"]} for r in d["result"]["requirements"]]
        cards.append({"kind": "call_type", "id": "call-type", "beat": 3, "tone": "blue",
                      "title": "Call type: certificate request", "source": d["source"],
                      "evidence": d["result"]["evidence"], "requirements": reqs})
    if n >= 4:
        d = detection(state, 3)
        rows, path = [], q.Path()
        for r in d["result"]["requirements"]:
            a = q.requirement_status(g, client(), r, party=contract())
            path.extend(a.path)
            rows.append({**a.answer, "name": g.nodes[r]["name"],
                         "form_label": q.label(g, a.answer["form"]) if a.answer["form"] else None,
                         "remedy_labels": [q.label(g, f) for f in a.answer["remedy_forms"]]})
        policy = rows[0]["policy"] if rows else None
        attached = [{"number": g.nodes[f]["number"], "name": g.nodes[f]["name"]}
                    for f, _ in q.out(g, policy, "ATTACHES")] if policy else []
        cards.append({"kind": "forms", "id": "forms", "beat": 4, "tone": "blue",
                      "title": "Forms on the GL against the contract",
                      "policy": g.nodes[policy] if policy else None, "attached": attached,
                      "rows": rows, "path": path_view(g, path)})
    if n >= 5:
        a = q.certificate_check(g, client(), contract())
        endorsement = state["decisions"].get("endorsement")
        cards.append({"kind": "certificate", "id": "certificate", "beat": 5,
                      "tone": "amber" if not a.answer["can_issue"] else "blue",
                      "title": "Certificate blocked" if not a.answer["can_issue"] else "Certificate can issue",
                      "a": a.answer, "endorsement": endorsement,
                      "forms": [q.label(g, f) for f in a.answer["endorsement_forms"]],
                      "words": suggested_words(g, a.answer["requirements"]),
                      "path": path_view(g, a.path)})
    cards.sort(key=lambda c: c["beat"], reverse=True)
    return cards
