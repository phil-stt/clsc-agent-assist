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
CARRIER = "Westbrook Mutual"
WRAP_KINDS = {"activity_note": "Activity note for the AMS",
              "endorsement_request": "Endorsement request to Westbrook Mutual",
              "follow_up_email": "Follow-up email to Marisol"}


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


def first_beat(state: dict, intent: str, after: int = 0) -> int | None:
    """The first beat so far whose detected intent is `intent`."""
    for n in range(after + 1, state["beat"] + 1):
        d = detection(state, n)
        if d and d["result"]["intent"] == intent:
            return n
    return None


def new_locations(r: dict) -> list[dict]:
    """Locations count as observed only on the beat that reports the change, not when the agent restates it at wrap."""
    return r["locations"] if r["intent"] == "location_change" else []


def new_exposures(r: dict) -> list[str]:
    """Same rule for exposures: the beat where the client reveals the change in operations."""
    return r["exposures"] if r["intent"] == "operations_change" else []


def world(state: dict) -> nx.MultiDiGraph:
    """The graph as it stands at this point in the call, observations included."""
    g = base_graph().copy()
    for n in range(1, state["beat"] + 1):
        d = detection(state, n)
        if not d:
            continue
        for loc in new_locations(d["result"]):
            slug = re.sub(r"[^a-z0-9]+", "-", loc["name"].lower()).strip("-")
            name = loc["name"][:1].upper() + loc["name"][1:]
            kg.observe_location(g, client(), slug, name, since=loc["when"])
        if "exposure:professional-services" in new_exposures(d["result"]):
            kg.observe_fact(g, client(), "design_work", True, "Design work now done in-house.",
                            as_of=call()["call"]["date"])
    return g


def raised_exposure(state: dict) -> tuple[int, str] | None:
    """(beat, exposure id) for the first exposure the client revealed, if any."""
    for n in range(1, state["beat"] + 1):
        d = detection(state, n)
        if d and new_exposures(d["result"]):
            return n, new_exposures(d["result"])[0]
    return None


def recommendation(g: nx.MultiDiGraph, state: dict) -> dict | None:
    """The product the graph recommends for the raised exposure, with its market and the carriers offering it."""
    raised = raised_exposure(state)
    if not raised:
        return None
    n, exp = raised
    a = q.cq6_exposure(g, client(), exp)
    if a.answer["covered"] or not a.answer["products"]:
        return None
    p = a.answer["products"][0]
    carriers = [q.label(g, c) for c, _ in q.out(g, p["product"], "OFFERED_BY")]
    return {"beat": n, "exposure": exp, "a": a, **p, "carriers": carriers}


def quote_in_play(state: dict) -> int | None:
    """The beat the agent moved to quote, if a product is recommended and the agent hasn't dismissed it."""
    rec = recommendation(base_graph(), state) if raised_exposure(state) else None
    dismissed = state["decisions"].get("product", {}).get("status") == "dismissed"
    if not rec or dismissed:
        return None
    return first_beat(state, "quote_request", after=rec["beat"])


def endorsement_items(g: nx.MultiDiGraph, a: q.Answer, with_locations: bool = True) -> list[str]:
    """Everything the contract needs from the GL, plus new locations: the itemized endorsement request."""
    items = [f"Add {q.label(g, f)} ({g.nodes[f]['name']})" for f in a.answer["endorsement_forms"]]
    for r in a.answer["requirements"]:
        if r["status"] == "if_scheduled":
            who = g.nodes[contract()]["counterparty"].replace(" (fictional)", "")
            items.append(f"Schedule {who} on {q.label(g, r['form'])} ({r['name'].lower()})")
    if with_locations:
        for loc in q.cq4_uncovered_locations(g, client()).answer["uncovered"]:
            since = g.nodes[loc].get("since")
            items.append(f"Add location: {q.label(g, loc)}" + (f" (leased {since})" if since else ""))
    return items


def endorsement_short(g: nx.MultiDiGraph, a: q.Answer) -> list[str]:
    """The same request, as form numbers for a button."""
    short = [q.label(g, f) for f in a.answer["endorsement_forms"]]
    short += [f"{q.label(g, r['form'])} schedule" for r in a.answer["requirements"] if r["status"] == "if_scheduled"]
    return short


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
    n = beat["n"]
    st.log(state, "system", "plain", "transcript", f"{beat['speaker'].title()}: {beat['text']}")
    if r["intent"] == "certificate_request":
        names = ", ".join(base_graph().nodes[x]["name"] for x in r["requirements"])
        st.log(state, "ai", "blue", "detect", f"{who}: certificate request. Requirements parsed: {names}.", source=src)
    if n == 2:
        st.log(state, "ai", "blue", "account", "Account pulled from the AMS record: Reyes Design Build, Inc.")
    if n == 4:
        g = world(state)
        a = q.cq2_contract_requirements(g, client(), contract())
        st.log(state, "ai", "blue", "forms", f"Forms read from the GL. {a.summary}.", path=a.path.edges)
    if n == 5:
        a = q.certificate_check(world(state), client(), contract())
        if not a.answer["can_issue"]:
            st.log(state, "ai", "amber", "block", "Certificate blocked: " + a.answer["reason"], path=a.path.edges)
    for loc in new_locations(r):
        st.log(state, "ai", "blue", "detect", f"{who}: new location mentioned, {loc['name']} ({loc['when']}).", source=src)
        a = q.cq4_uncovered_locations(world(state), client())
        st.log(state, "ai", "blue", "location",
               f"{a.summary}. Queued for the endorsement request to {CARRIER}.", path=a.path.edges)
    for exp in new_exposures(r):
        st.log(state, "ai", "blue", "detect", f"{who}: exposure raised, {base_graph().nodes[exp]['name']}.", source=src)
        rec = recommendation(world(state), state)
        if rec:
            st.log(state, "ai", "blue", "recommend", rec["a"].summary + " Awaiting the agent's decision.",
                   path=rec["a"].path.edges)
    qb = quote_in_play(state)
    if qb == n:
        g = world(state)
        a = q.cq3_disclosures(g, client(), recommendation(g, state)["product"])
        st.log(state, "ai", "blue", "disclosures", f"Disclosures surfaced. {a.summary}", path=a.path.edges)
    elif qb and n == qb + 1 and r["intent"] == "quote_request" and "ca-d1" not in state["marks"]:
        st.log(state, "ai", "amber", "nudge", "Client agreed to a quote. D-1 not yet delivered.")
    if r["intent"] == "decline":
        st.log(state, "ai", "blue", "decline",
               f"Client is thinking it over. Follow-up proposed for {call()['call']['follow_up_label']}.")
    if r["intent"] == "wrap" and not state["drafts"]:
        draft(state)


# --- Human actions ----------------------------------------------------------

MARKS = {"recorded_line": ("Recorded-line notice delivered", "delivered"),
         "ca-d1": ("D-1 sent for signature", "sent for signature"),
         "ca-broker-fee": ("Broker fee disclosure delivered", "delivered")}


def mark(state: dict, what: str) -> dict:
    label, how = MARKS.get(what, (what, "delivered"))
    state["marks"][what] = {"beat": state["beat"], "how": how}
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
    g = world(state)
    a = q.certificate_check(g, client(), contract())
    items = endorsement_items(g, a)
    state["decisions"]["endorsement"] = {"beat": state["beat"], "items": items,
                                         "forms": endorsement_short(g, a), "carrier": CARRIER}
    st.log(state, "agent", "green", "decision",
           f"Endorsement request started by agent to {CARRIER}: {'; '.join(items)}.")
    return state


def decide_product(state: dict, status: str) -> dict:
    """The agent confirms or dismisses the recommendation. Market selection is the agent's act."""
    rec = recommendation(world(state), state)
    if not rec or status not in ("confirmed", "dismissed"):
        return state
    state["decisions"]["product"] = {"beat": state["beat"], "status": status, "product": rec["product"],
                                     "name": rec["name"], "market": rec["market_kind"]}
    verb = "confirmed" if status == "confirmed" else "dismissed"
    st.log(state, "agent", "green", "decision",
           f"Recommendation {verb} by agent: {rec['name']}, {rec['market_kind']} market.")
    return state


def request_quote(state: dict) -> tuple[dict, dict]:
    """Human-only. A non-admitted submission is an application, and the D-1 is signed at application."""
    g = world(state)
    rec = recommendation(g, state)
    if not rec:
        return state, {"requested": False, "reason": "No product recommended."}
    if "ca-d1" not in state["marks"]:
        state["decisions"]["quote_blocked"] = {"beat": state["beat"]}
        reason = ("D-1 not yet delivered. A quote request to a non-admitted market goes out with the application, "
                  "and Cal. Ins. Code §1764.1(a)(1) requires the applicant's signature on the D-1 at application.")
        st.log(state, "agent", "amber", "refused", "Request quote blocked: " + reason)
        return state, {"requested": False, "reason": reason}
    state["decisions"]["quote"] = {"beat": state["beat"], "product": rec["name"], "market": rec["market_kind"],
                                   "carriers": rec["carriers"]}
    st.log(state, "agent", "green", "decision",
           f"Quote requested by agent: {rec['name']} from {', '.join(rec['carriers'])} "
           f"({rec['market_kind']}). Nothing bound.")
    return state, {"requested": True}


def accept_draft(state: dict, kind: str, title: str, body: str) -> dict:
    d = state["drafts"].get(kind)
    if not d:
        return state
    edited = (title.strip(), body.strip()) != (d["title"].strip(), d["body"].strip())
    d.update({"title": title.strip(), "body": body.strip(), "accepted": {"beat": state["beat"], "edited": edited}})
    st.log(state, "agent", "green", "decision",
           f"{WRAP_KINDS[kind]} accepted by agent{' with edits' if edited else ''}. Not sent.")
    return state


# --- The wrap -----------------------------------------------------------------

def wrap_facts(state: dict) -> dict:
    """The settled facts of the call, from the graph and the event record. Claude drafts from these only."""
    g = world(state)
    c = g.nodes[client()]
    cert = q.certificate_check(g, client(), contract())
    pol = g.nodes[cert.answer["requirements"][0]["policy"]]

    def status(r):
        if r["status"] == "satisfied":
            return f"on the policy ({q.label(g, r['form'])})"
        if r["status"] == "if_scheduled":
            return f"on the policy once scheduled: {r['condition']}"
        return f"not on the policy; needs {', '.join(q.label(g, f) for f in r['remedy_forms'])}"

    rec = recommendation(g, state)
    product = state["decisions"].get("product")
    marks = state["marks"]
    discs = [{"name": "Recorded-line notice",
              "status": "delivered at the start of the call" if "recorded_line" in marks else "not marked delivered"}]
    if rec:
        for row in q.cq3_disclosures(g, client(), rec["product"]).answer["disclosures"]:
            key = row["disclosure"].split(":", 1)[1]
            if key in marks:
                s = marks[key]["how"]
            elif row["signature_required"]:
                s = "not delivered; no application went out, so it goes with the application if she proceeds"
            else:
                s = "not delivered; goes with the quote"
            discs.append({"name": row["name"], "status": s})
    quote = state["decisions"].get("quote")
    meta = call()["call"]
    return {
        "call": {"date": meta["date"], "agency": g.nodes["agency:pacific-crest"]["name"],
                 "agent": meta["agent"].split(",")[0], "client": c["name"], "contact": c["contact"]},
        "request": f"Certificate of insurance for {g.nodes[contract()]['counterparty'].replace(' (fictional)', '')}, "
                   "needed before her crew starts work Monday.",
        "contract_requirements": [{"requirement": r["name"], "status": status(r)}
                                  for r in cert.answer["requirements"]],
        "certificate": {"issued": False, "why_not": cert.answer["reason"]} if not cert.answer["can_issue"]
        else {"issued": False, "why_not": "Not requested yet."},
        "endorsement_request": {
            "carrier": CARRIER, "policy": f"{pol['line']} {pol['number']}",
            "items": endorsement_items(g, cert),
            "started_by_agent_during_call": "endorsement" in state["decisions"]},
        "changes_since_underwriting_file": [f"{ch['now']} (file said: {ch['was']})"
                                            for ch in q.cq5_changes_since_underwriting(g, client()).answer["changes"]],
        "exposure_review": None if not rec else {
            "exposure": q.label(g, rec["exposure"]),
            "general_liability": f"excluded by {rec['a'].answer['excluded_by']}",
            "recommended_product": rec["name"], "market": rec["market_kind"],
            "agent_decision": product["status"] if product else "not decided on the call"},
        "disclosures": discs,
        "quote": (f"requested from {', '.join(quote['carriers'])}; nothing bound" if quote else "not requested"),
        "client_decision": "Wants the professional liability information in writing; will review it this weekend.",
        "follow_up": meta["follow_up_label"],
    }


def draft(state: dict) -> dict:
    facts = wrap_facts(state)
    d = llm.draft_wrap(facts)
    drafts, source = d["result"], d["source"]
    if drafts is None:
        drafts, source = template_drafts(facts), "template"
    state["drafts"] = {k: {**drafts[k], "source": source} for k in WRAP_KINDS}
    who = {"claude-cached": "Claude (cached)", "claude-live": "Claude", "template": "Template fallback"}[source]
    st.log(state, "ai", "blue", "wrap",
           f"{who}: wrap drafted (activity note, endorsement request, follow-up email). Awaiting agent review.",
           source=source)
    return state


def template_drafts(f: dict) -> dict:
    """Offline stand-in when there is no recorded response and no key: the same facts, filled into fixed text."""
    first = f["call"]["contact"].split()[0]
    agent = f["call"]["agent"].split()[0]
    e = f["endorsement_request"]
    ex = f["exposure_review"]
    note = [f"{f['call']['date']} · call with {f['call']['contact']} · {f['call']['agent']}",
            f"Request: {f['request']}",
            "Contract requirements against the GL:"]
    note += [f"- {r['requirement']}: {r['status']}" for r in f["contract_requirements"]]
    note += [f"Certificate not issued. {f['certificate']['why_not']}",
             f"Endorsement request to {e['carrier']}: " + "; ".join(e["items"]) + "."]
    note += [f"Changed since underwriting: {ch}" for ch in f["changes_since_underwriting_file"]]
    if ex:
        note.append(f"Exposure review: {ex['exposure']}; GL {ex['general_liability']}. Recommended "
                    f"{ex['recommended_product']} ({ex['market']}); agent decision: {ex['agent_decision']}.")
    note += [f"Disclosure, {d['name']}: {d['status']}." for d in f["disclosures"]]
    note += [f"Quote: {f['quote']}.", f"Client: {f['client_decision']}", f"Follow-up: {f['follow_up']}."]
    req = [f"Please endorse {e['policy']} for {f['call']['client']}:"]
    req += [f"{i}. {item}" for i, item in enumerate(e["items"], 1)]
    req += ["The first items answer the insurance requirements of the client's new contract; "
            "the location is a newly leased yard.",
            "Please confirm when the endorsements are processed so we can issue the certificate.",
            f"{agent}, {f['call']['agency']}"]
    email = [f"Hi {first},",
             f"Thanks for the call today. I've sent {e['carrier']} the request to add what the "
             "Larchmont contract needs to your general liability policy. As soon as they confirm, "
             "I'll send the certificate.",
             "I've also asked them to add the Vernon yard to the policy."]
    if ex:
        email.append(f"As promised, I'll send the {ex['recommended_product'].lower()} information in writing "
                     "so you can look it over this weekend.")
    email += [f"I'll check back with you on {f['follow_up']}.", f"{agent}", f["call"]["agency"]]
    return {"activity_note": {"title": f"Service call: {f['call']['client']}", "body": "\n".join(note)},
            "endorsement_request": {"title": f"Endorsement request: {e['policy']}", "body": "\n".join(req)},
            "follow_up_email": {"title": "Your certificate and next steps", "body": "\n\n".join(email)}}


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
        parts.append(f"It has {', '.join(sched)}, but Larchmont has to be added to that schedule.")
    if gaps:
        parts.append(f"It does not have {' or '.join(gaps)} yet, and a certificate can only show what the "
                     "policy actually has, so I can't send one today that shows those.")
    asks = gaps + [f"Larchmont added to {s}" for s in sched]
    if asks:
        parts.append(f"I'm sending Westbrook a request right now with everything the contract needs: "
                     f"{', '.join(asks[:-1]) + ', and ' + asks[-1] if len(asks) > 1 else asks[0]}. "
                     "I'll get you the certificate the moment they confirm, and I'll push to have it before Monday.")
    return " ".join(parts)


EXPOSURE_QUESTION = {
    "exposure:professional-services": "What design work does the architect do: full drawings and specs that "
                                      "others build from, or design on your own design-build jobs only? "
                                      "Roughly what share of revenue is design-build now?",
}


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
                      "mark": "recorded_line", "delivered": delivered, "button": "Mark delivered",
                      "done": "Delivered. Marked by the agent.",
                      "lede": "Read this verbatim before any account discussion."})
        if n >= 2 and not delivered:
            cards.append({"kind": "nudge", "id": "recorded-line-nudge", "beat": n + 0.5, "tone": "amber",
                          "title": "Recorded-line notice not marked delivered",
                          "body": "The call has moved on. California requires all parties to consent to "
                                  "recording; deliver the notice now and mark it.",
                          "mark": "recorded_line", "button": "Mark delivered", "citation": disc["citation"]})
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
    endorsement = state["decisions"].get("endorsement")
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
                      "rows": rows, "requested": bool(endorsement), "path": path_view(g, path)})
    if n >= 5:
        a = q.certificate_check(g, client(), contract())
        cards.append({"kind": "certificate", "id": "certificate", "beat": 5,
                      "tone": "amber" if not a.answer["can_issue"] else "blue",
                      "title": "Certificate blocked" if not a.answer["can_issue"] else "Certificate can issue",
                      "a": a.answer, "endorsement": endorsement,
                      "forms": endorsement_short(g, a), "items": endorsement_items(g, a, with_locations=False),
                      "words": suggested_words(g, a.answer["requirements"]),
                      "path": path_view(g, a.path)})
    loc_beat = first_beat(state, "location_change")
    if loc_beat:
        a = q.cq4_uncovered_locations(g, client())
        if a.answer["uncovered"]:
            cards.append({"kind": "location", "id": "location", "beat": loc_beat, "tone": "blue",
                          "title": "New location, not on the policy",
                          "locations": [g.nodes[l] for l in a.answer["uncovered"]],
                          "source": detection(state, loc_beat)["source"],
                          "evidence": detection(state, loc_beat)["result"]["evidence"],
                          "carrier": CARRIER, "path": path_view(g, a.path)})
        a = q.cq5_changes_since_underwriting(g, client())
        if a.answer["changes"]:
            cards.append({"kind": "drift", "id": "drift", "beat": loc_beat - 0.1, "tone": "blue",
                          "title": "Changed since the underwriting file", "changes": a.answer["changes"],
                          "path": path_view(g, a.path)})
    rec = recommendation(g, state)
    product = state["decisions"].get("product")
    if rec:
        d = detection(state, rec["beat"])
        cards.append({"kind": "exposure", "id": "exposure", "beat": rec["beat"],
                      "tone": "green" if product else "blue",
                      "title": f"Exposure: {q.label(g, rec['exposure']).lower()}",
                      "rec": rec, "a": rec["a"].answer, "decision": product,
                      "source": d["source"], "evidence": d["result"]["evidence"],
                      "question": EXPOSURE_QUESTION.get(rec["exposure"]),
                      "path": path_view(g, rec["a"].path)})
    qb = quote_in_play(state)
    if qb:
        a = q.cq3_disclosures(g, client(), rec["product"])
        quote = state["decisions"].get("quote")
        blocked = state["decisions"].get("quote_blocked")
        cards.append({"kind": "quote", "id": "quote", "beat": qb + 0.3,
                      "tone": "green" if quote else "blue",
                      "title": f"Quote: {rec['name']}", "rec": rec, "quote": quote,
                      "disclosures": a.answer["disclosures"]})
        for i, row in enumerate(a.answer["disclosures"]):
            key = row["disclosure"].split(":", 1)[1]
            m = state["marks"].get(key)
            sig = row["signature_required"]
            cards.append({"kind": "disclosure", "id": key, "beat": qb + 0.2 - i * 0.05,
                          "tone": "green" if m else "blue", "title": row["name"],
                          "disclosure": kg.read_disclosure(g, row["disclosure"]), "mark": key,
                          "delivered": bool(m), "exemption": row["exemption"], "trigger": row["citation"],
                          "button": "Mark sent for signature" if sig else "Mark delivered",
                          "done": ("Sent for signature. Marked by the agent." if sig
                                   else "Delivered. Marked by the agent."),
                          "lede": ("Non-admitted placement, California home state. The applicant signs this notice "
                                   "at application. Deliver it verbatim." if sig else
                                   "The agency charges a broker fee on non-admitted placements. "
                                   "Disclose it with the quote. Deliver it verbatim."),
                          "path": path_view(g, a.path) if i == 0 else []})
        decline = first_beat(state, "decline", after=qb)
        d1_open = "ca-d1" not in state["marks"]
        if d1_open and (blocked or (n > qb and not decline)):
            d1 = kg.read_disclosure(g, "disclosure:ca-d1")
            cards.append({"kind": "skip", "id": "d1-skip", "beat": n + 0.6, "tone": "amber",
                          "title": "D-1 not yet delivered",
                          "body": ("You tried to request the quote before the D-1. " if blocked else
                                   "Marisol agreed to a quote. ") +
                                  "A quote request to a non-admitted market goes out with the application, and the "
                                  "applicant signs the D-1 at application. Deliver it now, then request the quote.",
                          "disclosure": d1, "mark": "ca-d1", "button": "Mark sent for signature"})
    decline = first_beat(state, "decline")
    if decline:
        quote = state["decisions"].get("quote")
        rows = []
        if rec:
            rows.append(("Exposure raised", f"{q.label(g, rec['exposure'])}; the GL excludes it "
                                            f"({rec['a'].answer['excluded_by']})"))
            rows.append(("Product recommended", f"{rec['name']}, {rec['market_kind']} market. Agent: "
                         + (product["status"] if product else "not decided")))
            for row in q.cq3_disclosures(g, client(), rec["product"]).answer["disclosures"]:
                key = row["disclosure"].split(":", 1)[1]
                m = state["marks"].get(key)
                rows.append((row["name"], m["how"].capitalize() if m else
                             ("Not delivered. No application went out; it goes with the application if she proceeds."
                              if row["signature_required"] else "Not delivered. It goes with the quote.")))
            rows.append(("Quote", f"Requested from {', '.join(quote['carriers'])}" if quote else "Not requested"))
        rows.append(("Client", "Wants it in writing; reviewing this weekend"))
        cards.append({"kind": "decline", "id": "decline", "beat": decline, "tone": "blue",
                      "title": "Client is thinking it over", "rows": rows,
                      "follow_up": call()["call"]["follow_up_label"]})
    wrap = first_beat(state, "wrap")
    if wrap and state["drafts"]:
        for i, (kind, label) in enumerate(WRAP_KINDS.items()):
            d = state["drafts"][kind]
            cards.append({"kind": "draft", "id": f"draft-{kind.replace('_', '-')}", "beat": wrap + 0.3 - i * 0.1,
                          "tone": "green" if d.get("accepted") else "blue", "title": label,
                          "wrap_kind": kind, "d": d})
    cards.sort(key=lambda c: c["beat"], reverse=True)
    return cards
