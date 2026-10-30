# Agent Assist for Commercial Lines Service Calls

Every regulated client call, guided as it happens: the client's own policy data, the right endorsement, the exact disclosure at the right beat, and a clean file when the call ends.

**Business area:** Retail independent agency, commercial lines service and account management.
**Main AI role:** A real-time co-pilot on a live client call that knows the account, follows the call, surfaces what to pull and what to say next, keeps the licensed agent compliant in the moment, and drafts the after-call work.

*This is a self-authored design brief for a prototype. All companies, people, policy numbers and figures are made up. Statutes and form numbers are real and cited where they matter; treat them as the shape of the compliance problem, not as legal advice.*

**Why this matters:** Commercial insurance is sold and serviced by conversation. The products are hard to explain, the paperwork is contract-driven, and a licensed agent carries personal liability for what they say about coverage. The service call is the highest-volume, most heavily regulated touchpoint the agency has, and it is where cross-sell happens or doesn't. An agency that gets this call right grows the account, keeps the E&O carrier happy, and keeps its license.

---

## The problem

A commercial lines account manager at a retail agency handles multi-step, regulated calls all day: certificate of insurance (COI) requests, endorsements (add a location, a vehicle, an additional insured), limit changes, renewal check-ins, billing. On a single call they must pull the client's current coverage from the agency management system, read the actual endorsements on the policy before they represent anything on a certificate, spot the exposures the client is not insured for, know which of those products will have to go to the surplus lines market, and say the state-mandated words when they do. All while a business owner is on the line and in a hurry.

Today they do it by tenure and tabs. The policy is in the AMS, the forms are PDFs, the carrier appetite guide is an email from March, the surplus lines disclosure is a form in a shared drive, and the broker fee agreement is in a different shared drive. The firmographic picture of the client (industry, payroll, revenue, locations, what they said at underwriting) lives in the application from two years ago.

The results: COIs that show coverage the policy does not actually give (the single biggest E&O exposure in an agency); missed or paraphrased surplus lines disclosures; cross-sell that never happens because the agent is busy finishing the task the client called about; long handle times; after-call documentation that is thin or late; and a 12-to-18 month ramp for a new account manager.

The information needed for one call is spread across the AMS, carrier portals, ISO and carrier form libraries, state regulatory text, the agency's own compliance documents, and the client's underwriting file. No single view holds it.

## Scenario (illustrative, made-up)

Marisol Reyes owns Reyes Design Build, an 18-person general contractor in Los Angeles that does commercial tenant improvements. She calls her agency because a new client, a property management firm, needs a certificate of insurance before her crew can start Monday. The contract requires additional insured status for ongoing and completed operations, primary and noncontributory wording, and a waiver of subrogation.

The account manager has to check whether her general liability policy actually carries those endorsements (it has a blanket additional insured endorsement for ongoing operations and nothing for completed operations), say so honestly, and start the endorsement request rather than issue a certificate that implies coverage she does not have. Mid-call Marisol mentions she leased a yard in Vernon last month, which is an unreported location. She also mentions, in passing, that she has started doing design work in-house. That is a professional liability exposure her GL policy excludes, the likely market for it is non-admitted, and placing it in California means a signed D-1 disclosure at application, a written broker fee agreement if the agency charges a fee, and a five-day cancellation right if the coverage is bound before she signs.

Three regulated moments in one eleven-minute call. The agent has to catch all three, say the right words at each one, and not lose a client who called about a certificate.

## Why now

Agency E&O claims driven by certificate errors and failure-to-recommend-coverage are a known, recurring category, and QA at most agencies is a file audit weeks later. The surplus lines share of commercial placements keeps growing, which means more calls where a statutory disclosure is required. Account manager tenure is falling and the knowledge that made the job work was always in people's heads. And AI can now follow a live conversation, ground its answers in the client's own policy forms, and enforce a disclosure in the moment rather than catch its absence in an audit. (Figures cited anywhere in this project are illustrative and labeled as such.)

## Who it is for

* Commercial lines account managers and CSRs (the main character)
* Producers on renewal and cross-sell calls
* Agency principal and compliance / E&O risk lead

## What great looks like (and what weak looks like)

**Great:** a live call where the AI detects the call type (certificate request), pulls the client's real (fake) policy and reads the endorsements actually attached, tells the agent in-flow that completed-operations coverage is missing before a certificate goes out, catches the unreported location and queues the endorsement, recognizes the professional liability exposure from what the client said and surfaces the product with its market (non-admitted), surfaces the exact D-1 text and the broker fee disclosure at the moment the agent moves to quote, flags the disclosure as not yet delivered if the agent skips it, and drafts the activity note, the endorsement request, and the follow-up email. The AI changes the outcome of the call.

**Weak:** a chatbot side panel that answers typed questions with generic text about what general liability is, cannot see the policy, does not know which state's rules apply, and leaves the certificate, the disclosure and the file note to the human. A wrapper.

## What this project covers

1. **Problem brief.** The problem, the user, and why now. The compliance pain and the revenue opportunity.
2. **Service design.** The current end-to-end account manager journey (before, during, after the call) and the future journey. The E&O exposure and the handle-time pain made visible, and the improvement obvious.
3. **Working prototype.** An interactive demo. Not production-ready. It shows: (a) live call context grounded in the client's account and policy forms, (b) a coverage gap caught in-flow before a certificate is issued, (c) the correct state disclosure surfaced at the right beat, with a real-time nudge when it is skipped, and (d) an auto-drafted wrap: activity note, endorsement request, and client follow-up.
4. **Product roadmap.** A phased plan with the reason for the order.
5. **Key tradeoff.** One real tradeoff made and why.

## Where AI decides, recommends, or hands off

| AI decides (autonomous) | AI recommends (human confirms) | Human only (AI hands off) |
| ----- | ----- | ----- |
| Detect call type and intent; pull the account and the forms on the policy; detect a missed or paraphrased disclosure; draft the activity note, endorsement request and follow-up email | Coverage gaps to raise; which product and which market (admitted vs. surplus lines); next best question for the exposure review; which endorsement form answers the contract requirement; disposition | Represent coverage on a certificate; quote or bind anything; decide that a risk goes to the non-admitted market; deliver and obtain the signed disclosure; agree a broker fee; give legal or contract advice |

## Sample data (made-up)

* **Agency:** Pacific Crest Insurance Services, Los Angeles. Retail independent agency, broker-agent license, home state California for every account in the demo (so one state's rules apply; see Stretch for a second state).
* **Client:** Reyes Design Build, Inc. NAICS 236220 (commercial building construction). 18 employees. $4.2M revenue. Two locations: office in Los Angeles, and a yard in Vernon leased last month that is not on the policy. Underwriting file notes: "no design work; subcontracts all electrical and plumbing." That note is now stale, which is the point.
* **Policies in force (illustrative):**
  1. Commercial General Liability, admitted carrier "Westbrook Mutual," $1M per occurrence / $2M aggregate. Endorsements attached: CG 20 33 (automatic additional insured, ongoing operations, when required by contract), CG 24 04 (waiver of subrogation, scheduled). Not attached: CG 20 37 (completed operations), CG 20 01 (primary and noncontributory).
  2. Commercial Auto, admitted, 3 vehicles.
  3. Workers' compensation, admitted (out of scope for the demo beyond showing it exists).
  4. No professional liability. No cyber.
* **Product and enhancements library (illustrative):** CGL with the endorsement set above; Contractors Professional Liability (market: non-admitted, two illustrative carriers); Cyber Liability (one admitted option, one non-admitted); Hired and Non-Owned Auto; Umbrella. Each product carries: who it is for (NAICS ranges, revenue bands), what it covers in one paragraph, its market, and the disclosures it triggers.
* **The three required compliance beats** (the "verbatim" of this use case):
  1. **Recorded-line notice** at the top of the call. California is a two-party consent state; the agency's approved greeting is Legal's text, the AI surfaces it.
  2. **California surplus lines disclosure (D-1)** when any non-admitted product is proposed. The statutory wording is set in California Insurance Code §1764.1 and must be signed by the applicant at application; the applicant may cancel within five days of receiving it if coverage was bound first, with premium prorated and any broker fee returned. Renewals use the D-2. An "industrial insured" (25+ employees and $25K+ in annual premium, roughly) is exempt from signing. Reyes has 18 employees, so the exemption does not apply, and the demo shows the AI checking that.
  3. **Broker fee disclosure** if the agency charges a fee on the placement: in California the fee must be set in a written broker fee agreement, and the fact that a fee may be charged is disclosed with the initial quote.
* **The certificate rule:** the AI must prevent, and the agent must never commit, a representation on a certificate that the policy does not support. Most states have certificate-of-insurance laws that say a certificate does not amend, extend or alter the policy, and many prohibit misrepresenting coverage. The demo shows the gap (no CG 20 37) and routes to an endorsement request rather than to a certificate.
* **Flow:** identify and recorded-line notice → certificate request → read forms → gap found → endorsement started → location discovered → exposure review (design work) → product recommended, market identified → disclosures surfaced → quote request or decline → wrap.

## The knowledge layer (the architecture question this project exists to explore)

The reason this call is hard is that the facts an agent needs are relationships: this client, in this state, has this policy, with these forms attached, which answer these contract requirements and not those; this product, for this industry at this size, is placed in this market, which triggers this disclosure in this state. That is a graph before it is anything else. The project decides how to build and consume it, and defends the choice.

Three approaches compared:

* **A. Curated ontology, property graph.** Hand-model the entities (Client, Location, Policy, Coverage, Form/Endorsement, Carrier, Market, Product, Industry, State, Rule, Disclosure, Contract Requirement) and their edges, load the fake data, and have the AI query the graph for every grounded answer. Most auditable; every answer has a path. Slowest to extend.
* **B. LLM-extracted graph (GraphRAG).** Point the model at the policy forms, the product sheets and the regulatory text, let it extract entities and relationships, and retrieve over the result. Fastest to stand up. The question is whether you trust what it extracted on a regulated call, and how a human approves it.
* **C. Hybrid.** A small curated schema (the entity types and the edges that carry compliance meaning), populated by LLM extraction from documents, with a human approval step for anything that changes a disclosure rule or a coverage relationship. Then plain RAG over the long-form text (the form itself, the statute) for the citation.

Competency questions come first, and each approach is tested against them. Examples: "Does this policy give completed-operations additional insured status to a scheduled party?" "Which disclosures does this product trigger for a client whose home state is California with 18 employees?" "Which forms on this policy answer this contract's requirements, and which requirement is unanswered?" "What changed on this account since the underwriting file was written?" If an approach cannot answer those with a traceable path, it does not belong on a regulated call. The decision and the full question set are in `knowledge-layer.md`.

## Principles

* **Prototype to think.** A working call in two days beats a spec in two weeks.
* **Architecture first.** Separate content from workflow. The product library, the form library and the disclosure rules are one governed source that the live call, the after-call QA, and the renewal review all read.
* **The licensed agent's words are the regulated object.** The AI guides; the agent speaks and decides.
* **Start from the frontline.** The account manager and the business owner on the line.
* **The layer outlives the feature.** This call is one consumer of the knowledge layer; the roadmap is sequenced so the layer earns its keep elsewhere.

## Rules

Made-up data only. No real client, policy, carrier or claims data. Statutory text may be quoted from public sources and is labeled with its citation.

A human stays in the loop where it matters. Binding, quoting, certificate representations, market selection and disclosure delivery are regulated and serious. The AI never issues a certificate, never binds, never tells a client a product is "covered," and never invents disclosure text. Disclosure wording is owned by the statute and the agency's compliance lead; the AI surfaces it.

## Stretch

* Show the same knowledge that guided the agent also scoring the call afterward: guided text equals graded text.
* Add a second home state (say, Texas or New York) and show the disclosure beat change without changing the call flow. That is the knowledge layer earning its keep.
* Estimate the effect on new account manager ramp time.

---

*Sources consulted for the compliance shape of this brief: California Insurance Code §1764.1 and the Surplus Line Association of California FAQ on the D-1/D-2 disclosure; the NRRA home-state and exempt commercial purchaser rules as summarized by NAIC and Insurance Journal; California Insurance Code §1623 and CCR Title 10 §2189 on broker fees; California Insurance Code §384 and IIABA and PIA summaries of state certificate-of-insurance laws; ISO endorsement references for CG 20 10, CG 20 37, CG 20 01, CG 20 33, CG 24 04 and CG 22 79.*
