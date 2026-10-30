"""Competency questions over the knowledge graph.

Every function returns an Answer: the result plus the Path it walked (node ids
and edge ids, in walk order). The UI's "show path" and the CQ tests both read
the path; an answer with an empty path is not an answer.

Nothing here calls a model. Forms matching, disclosure selection and the
exemption check are graph walks, so they come out the same every time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx


@dataclass
class Path:
    nodes: list[str] = field(default_factory=list)
    edges: list[str] = field(default_factory=list)

    def node(self, nid: str) -> None:
        if nid not in self.nodes:
            self.nodes.append(nid)

    def edge(self, data: dict, src: str, dst: str) -> None:
        self.node(src)
        if data["id"] not in self.edges:
            self.edges.append(data["id"])
        self.node(dst)

    def extend(self, other: "Path") -> None:
        for n in other.nodes:
            self.node(n)
        for e in other.edges:
            if e not in self.edges:
                self.edges.append(e)

    def __bool__(self) -> bool:
        return bool(self.edges)


@dataclass
class Answer:
    question: str
    answer: Any
    summary: str
    path: Path


def out(g: nx.MultiDiGraph, nid: str, etype: str):
    for _, dst, data in g.out_edges(nid, data=True):
        if data["type"] == etype:
            yield dst, data


def into(g: nx.MultiDiGraph, nid: str, etype: str):
    for src, _, data in g.in_edges(nid, data=True):
        if data["type"] == etype:
            yield src, data


def gl_policy(g: nx.MultiDiGraph, client: str, path: Path) -> str:
    for pol, data in out(g, client, "HAS"):
        if g.nodes[pol]["line"] == "Commercial General Liability":
            path.edge(data, client, pol)
            return pol
    raise LookupError(f"{client} has no GL policy")


def home_state(g: nx.MultiDiGraph, client: str, path: Path) -> str:
    for st, data in out(g, client, "HOME_STATE"):
        path.edge(data, client, st)
        return st
    raise LookupError(f"{client} has no home state")


def label(g: nx.MultiDiGraph, nid: str) -> str:
    n = g.nodes[nid]
    return n.get("number") or n.get("name") or nid


# --- The account card -------------------------------------------------------

def account_summary(g: nx.MultiDiGraph, client: str) -> Answer:
    path = Path()
    c = g.nodes[client]
    industry = None
    for ind, data in out(g, client, "IN"):
        path.edge(data, client, ind)
        industry = g.nodes[ind]
    home_state(g, client, path)
    policies = []
    for pol, data in out(g, client, "HAS"):
        path.edge(data, client, pol)
        carrier = None
        for car, cd in out(g, pol, "WRITTEN_BY"):
            path.edge(cd, pol, car)
            carrier = g.nodes[car]
        p = g.nodes[pol]
        policies.append({"id": pol, "line": p["line"], "number": p["number"],
                         "carrier": carrier["name"], "market": carrier["market"],
                         "limits": p["limits"], "effective": p["effective"], "expires": p["expires"],
                         "vehicles": p.get("vehicles")})
    locations = []
    for loc, data in out(g, client, "OPERATES_AT"):
        path.edge(data, client, loc)
        locations.append(g.nodes[loc]["name"])
    return Answer(question="Who is calling, and what do they have in force?",
                  answer={"name": c["name"], "contact": c["contact"], "naics": c["naics"],
                          "industry": industry["name"] if industry else None,
                          "employees": c["employees"], "revenue": c["revenue"],
                          "home_state": c["home_state"], "policies": policies, "locations": locations},
                  summary=f"{c['name']}: {len(policies)} policies in force.", path=path)


# --- Forms against contract requirements (CQ1, CQ2) ------------------------

def requirement_status(g: nx.MultiDiGraph, client: str, req: str,
                       party: str | None = None) -> Answer:
    """Is this contract requirement answered by a form attached to the GL?"""
    path = Path()
    policy = gl_policy(g, client, path)
    attached = {}
    for form, data in out(g, policy, "ATTACHES"):
        path.edge(data, policy, form)
        attached[form] = data

    status, by, condition = "unanswered", None, None
    for form, att in attached.items():
        for target, sat in out(g, form, "SATISFIES"):
            if target != req:
                continue
            path.edge(sat, form, target)
            scheduled = att.get("scheduled_parties")
            if scheduled is not None and party not in scheduled:
                status, by = "if_scheduled", form
                who = g.nodes[party].get("counterparty", label(g, party)).replace(" (fictional)", "") if party else "The party"
                condition = f"{who} must be added to the {label(g, form)} schedule"
            else:
                status, by, condition = "satisfied", form, sat.get("condition")
            break
        if status == "satisfied":
            break

    # Name the form that would answer it, so the gap routes somewhere.
    remedy = []
    if status == "unanswered":
        path.node(req)
        for form, sat in into(g, req, "SATISFIES"):
            if form not in attached:
                path.edge(sat, form, req)
                remedy.append(form)

    req_name = label(g, req)
    if status == "satisfied":
        summary = f"{req_name}: yes, {label(g, by)} is attached."
    elif status == "if_scheduled":
        summary = f"{req_name}: yes once scheduled. {condition}."
    else:
        forms = ", ".join(label(g, f) for f in remedy) or "no known form"
        summary = f"{req_name}: no. Not on the policy; answered by {forms}."
    return Answer(
        question=f"Does {label(g, policy)} answer '{req_name}'?",
        answer={"requirement": req, "status": status, "form": by,
                "condition": condition, "remedy_forms": remedy, "policy": policy},
        summary=summary, path=path)


def cq1_completed_ops(g: nx.MultiDiGraph, client: str) -> Answer:
    a = requirement_status(g, client, "req:ai-completed")
    a.question = ("Does the GL give completed-operations additional insured "
                  "status to a scheduled party?")
    return a


def cq2_contract_requirements(g: nx.MultiDiGraph, client: str, contract: str) -> Answer:
    path = Path()
    for c, data in out(g, client, "PARTY_TO"):
        if c == contract:
            path.edge(data, client, contract)
    rows = []
    for req, data in out(g, contract, "REQUIRES"):
        path.edge(data, contract, req)
        a = requirement_status(g, client, req, party=contract)
        path.extend(a.path)
        rows.append({**a.answer, "name": label(g, req), "summary": a.summary})
    gaps = [r for r in rows if r["status"] == "unanswered"]
    summary = (f"{len(rows) - len(gaps)} of {len(rows)} answered; unanswered: "
               + ", ".join(r["name"] for r in gaps)) if gaps else "All requirements answered."
    return Answer(question=f"Which of {label(g, contract)}'s requirements does the policy answer?",
                  answer={"requirements": rows, "gaps": [r["requirement"] for r in gaps]},
                  summary=summary, path=path)


# --- Disclosures (CQ3) -----------------------------------------------------

def markets_for(g: nx.MultiDiGraph, client: str, product: str, path: Path) -> list[str]:
    st_code = home_state(g, client, path).split(":", 1)[1]
    naics = g.nodes[client]["naics"]
    found = []
    for market, data in out(g, product, "PLACED_IN"):
        if data.get("state") != st_code:
            continue
        if not any(naics.startswith(p) for p in data.get("naics_prefixes", [""])):
            continue
        path.edge(data, product, market)
        found.append(market)
    return found


def exemption_applies(g: nx.MultiDiGraph, client: str, rule: str,
                      annual_premium: float | None) -> tuple[bool, str]:
    r, c = g.nodes[rule], g.nodes[client]
    employees_ok = c["employees"] >= r["min_employees"]
    premium_ok = annual_premium is not None and annual_premium >= r["min_annual_premium"]
    if employees_ok and premium_ok:
        return True, f"{c['employees']} employees and ${annual_premium:,.0f} premium meet both tests"
    reason = f"{c['employees']} employees, threshold {r['min_employees']}"
    if not employees_ok:
        return False, f"{reason}: exemption does not apply"
    return False, f"premium below ${r['min_annual_premium']:,}: exemption does not apply"


def cq3_disclosures(g: nx.MultiDiGraph, client: str, product: str,
                    annual_premium: float | None = None) -> Answer:
    path = Path()
    markets = markets_for(g, client, product, path)
    # A product with more than one market (cyber) needs the agent to pick; this
    # question is asked once the market is known, so take the non-admitted one
    # if it's the only placement, otherwise report per market.
    agency = None
    for a, data in out(g, client, "SERVICED_BY"):
        path.edge(data, client, a)
        agency = a
    rows = []
    for market in markets:
        kind = g.nodes[market]["kind"]
        for disc, data in out(g, market, "TRIGGERS"):
            if data.get("state") != g.nodes[client]["home_state"]:
                continue
            path.edge(data, market, disc)
            if "broker fee" in (data.get("condition") or ""):
                if kind not in g.nodes[agency].get("charges_broker_fee_on", []):
                    continue
            row = {"disclosure": disc, "name": label(g, disc), "market": market,
                   "citation": data.get("citation"),
                   "signature_required": bool(g.nodes[disc].get("signature_required")),
                   "exempt": False, "exemption": None}
            for rule, ex in out(g, disc, "EXEMPT_WHEN"):
                path.edge(ex, disc, rule)
                exempt, why = exemption_applies(g, client, rule, annual_premium)
                row["exemption"] = {"rule": rule, "applies": exempt, "reason": why,
                                    "citation": g.nodes[rule]["citation"]}
                if exempt and ex.get("waives") == "signature":
                    row["exempt"], row["signature_required"] = True, False
            rows.append(row)
    names = "; ".join(r["name"] + (f" ({r['exemption']['reason']})" if r["exemption"] else "")
                      for r in rows) or "none"
    return Answer(question=f"Which disclosures does {label(g, product)} trigger for this client?",
                  answer={"markets": markets, "disclosures": rows},
                  summary=f"{label(g, product)}: {names}.", path=path)


# --- Locations and drift (CQ4, CQ5) ----------------------------------------

def cq4_uncovered_locations(g: nx.MultiDiGraph, client: str) -> Answer:
    path = Path()
    policy = gl_policy(g, client, path)
    operated = {}
    for loc, data in out(g, client, "OPERATES_AT"):
        path.edge(data, client, loc)
        operated[loc] = data
    covered = set()
    for loc, data in out(g, policy, "COVERS"):
        path.edge(data, policy, loc)
        covered.add(loc)
    missing = [loc for loc in operated if loc not in covered]
    summary = ("Not on the policy: " + ", ".join(label(g, l) for l in missing)) if missing \
        else "Every location is on the policy."
    return Answer(question="Which locations does the client operate at that the policy doesn't cover?",
                  answer={"uncovered": missing, "covered": sorted(covered)},
                  summary=summary, path=path)


def cq5_changes_since_underwriting(g: nx.MultiDiGraph, client: str) -> Answer:
    path = Path()
    by_topic: dict[str, list[tuple[str, dict]]] = {}
    for fact, data in into(g, client, "ABOUT"):
        path.edge(data, fact, client)
        by_topic.setdefault(g.nodes[fact]["topic"], []).append((fact, g.nodes[fact]))

    changes = []
    for topic, facts in by_topic.items():
        filed = [f for f in facts if f[1]["source"] == "underwriting file"]
        later = sorted((f for f in facts if f[1]["source"] != "underwriting file"),
                       key=lambda f: f[1]["as_of"])
        if filed and later and later[-1][1]["value"] != filed[0][1]["value"]:
            changes.append({"topic": topic, "was": filed[0][1]["text"], "was_as_of": filed[0][1]["as_of"],
                            "now": later[-1][1]["text"], "now_as_of": later[-1][1]["as_of"],
                            "facts": [filed[0][0], later[-1][0]]})

    # Locations: the file's list against what the client operates at today.
    filed_locs = next((f for f in by_topic.get("locations", []) if f[1]["source"] == "underwriting file"), None)
    if filed_locs:
        for loc, data in out(g, client, "OPERATES_AT"):
            if loc not in filed_locs[1]["value"]:
                path.edge(data, client, loc)
                changes.append({"topic": "locations", "was": filed_locs[1]["text"],
                                "was_as_of": filed_locs[1]["as_of"],
                                "now": f"New location: {label(g, loc)}"
                                       + (f" (since {g.nodes[loc]['since']})" if g.nodes[loc].get("since") else ""),
                                "now_as_of": g.nodes[loc].get("since"), "facts": [filed_locs[0], loc]})
    summary = "; ".join(c["now"] for c in changes) or "No changes since the underwriting file."
    return Answer(question="What changed on this account since the underwriting file was written?",
                  answer={"changes": changes}, summary=summary, path=path)


# --- Exclusions (CQ6) ------------------------------------------------------

def cq6_exposure(g: nx.MultiDiGraph, client: str, exposure: str) -> Answer:
    path = Path()
    policy = gl_policy(g, client, path)
    excluded_by = None
    for cov, data in out(g, policy, "HAS_COVERAGE"):
        path.edge(data, policy, cov)
        for exp, ex in out(g, cov, "EXCLUDES"):
            if exp == exposure:
                path.edge(ex, cov, exp)
                excluded_by = ex.get("via_form")
    products = []
    for prod, data in out(g, exposure, "ADDRESSED_BY"):
        path.edge(data, exposure, prod)
        for market in markets_for(g, client, prod, path):
            products.append({"product": prod, "name": label(g, prod), "market": market,
                             "market_kind": g.nodes[market]["kind"]})
    covered = excluded_by is None
    if covered:
        summary = f"No exclusion found on the GL for {label(g, exposure)}."
    else:
        rec = ", ".join(f"{p['name']} ({p['market_kind']})" for p in products)
        summary = f"No. The GL excludes it ({excluded_by}). Addressed by {rec}."
    return Answer(question=f"Does the GL cover {label(g, exposure)}?",
                  answer={"covered": covered, "excluded_by": excluded_by, "products": products},
                  summary=summary, path=path)


# --- The certificate (CQ7) -------------------------------------------------

def certificate_check(g: nx.MultiDiGraph, client: str, contract: str) -> Answer:
    """Can a certificate showing this contract's requirements be issued today?"""
    path = Path()
    reqs = cq2_contract_requirements(g, client, contract)
    path.extend(reqs.path)
    state = home_state(g, client, path)
    rule = None
    for r, data in into(g, state, "APPLIES_IN"):
        if r == "rule:certificate-representation":
            path.edge(data, r, state)
            rule = r
    gaps = [r for r in reqs.answer["requirements"] if r["status"] == "unanswered"]
    remedy = [f for r in gaps for f in r["remedy_forms"]]
    can_issue = not gaps
    reason = (f"The policy does not carry {', '.join(label(g, f) for f in remedy)}. "
              f"A certificate cannot show {', '.join(r['name'].lower() for r in gaps)}. "
              f"{g.nodes[rule]['note']}") if gaps else "The attached forms answer every requirement."
    return Answer(
        question=f"Can a certificate be issued today for {label(g, contract)}?",
        answer={"can_issue": can_issue, "human_only": bool(g.nodes[rule]["human_only"]),
                "reason": reason, "citation": g.nodes[rule]["citation"],
                "gaps": [r["requirement"] for r in gaps],
                "endorsement_forms": remedy, "requirements": reqs.answer["requirements"]},
        summary=("No. " if gaps else "Yes, by a licensed agent. ") + reason, path=path)


def cq7_certificate(g: nx.MultiDiGraph, client: str, contract: str) -> Answer:
    return certificate_check(g, client, contract)


def provenance(g: nx.MultiDiGraph, path: Path) -> list[dict]:
    """Review provenance for every edge on a path that came in through the review screen."""
    found = []
    for eid in path.edges:
        src, dst = eid.split(":", 2)[2].split(">")
        for p in g.edges[src, dst, eid].get("provenance", []):
            found.append({"edge": eid, **p})
    return found
