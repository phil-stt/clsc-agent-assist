# The knowledge layer: why C, and what it has to answer

*2026-10-29. The architecture question the project exists to explore. Decision first, tests second, write-up argument third.*

## Decision
**Approach C, the hybrid.** A small curated schema holds the entity types and the edges that carry compliance meaning. LLM extraction reads the synthetic form, product and statute documents and *proposes* edges into a review queue. A person approves anything that changes a disclosure rule or a coverage relationship. Plain RAG over the long text (the endorsement form, the statute) supplies the citation when the UI needs to show words.

The one-line defense: on a regulated call every answer needs a path you can point at, and nobody has time to hand-model every form a carrier ships. A keeps the path and loses the speed. B keeps the speed and asks you to trust an unreviewed extraction when a licensed agent's words are on the line. C puts the review step exactly where the liability is and nowhere else.

## The schema (curated, small)
Entity types: `Client`, `Location`, `Policy`, `Coverage`, `Form` (endorsement), `Carrier`, `Market` (admitted / non-admitted), `Product`, `Industry` (NAICS), `State`, `Rule`, `Disclosure`, `ContractRequirement`, `UnderwritingFact`.

Edges that carry compliance meaning (these need human approval when extraction proposes or changes them):
- `Form -SATISFIES-> ContractRequirement` (CG 20 37 satisfies "additional insured, completed operations")
- `Product -PLACED_IN-> Market` scoped by `State` and `Industry`
- `Market -TRIGGERS-> Disclosure` scoped by `State`
- `Disclosure -EXEMPT_WHEN-> Rule` (industrial insured: 25+ employees and $25K+ premium)
- `Coverage -EXCLUDES-> Exposure` (GL excludes professional services)

Edges that are plain data and load straight in: `Client -HAS-> Policy`, `Policy -ATTACHES-> Form`, `Client -OPERATES_AT-> Location`, `Policy -COVERS-> Location`, `Client -IN-> Industry`, `Client -HOME_STATE-> State`, `UnderwritingFact -ABOUT-> Client` with an `as_of` date.

## Competency questions
Each one is a test in the repo. A passing answer returns the result **and the path** (the nodes and edges it walked). No path, no pass.

| # | Question | Expected answer on the demo data | Path shape |
|---|---|---|---|
| CQ1 | Does Reyes's GL policy give completed-operations additional insured status to a scheduled party? | **No.** CG 20 33 is attached (ongoing ops only); CG 20 37 is not. | Client → Policy → attached Forms → Form.SATISFIES → ContractRequirement; the completed-ops requirement has no satisfying form attached |
| CQ2 | Which of the property manager's 3 contract requirements does the policy answer, and which is unanswered? | AI ongoing ops: yes (CG 20 33). Waiver of subrogation: yes (CG 24 04, if the party is scheduled). Completed ops: **no**. Primary and noncontributory: **no** (CG 20 01 not attached). | Same as CQ1, iterated over requirements |
| CQ3 | Which disclosures does Contractors Professional Liability trigger for a California client with 18 employees? | D-1 surplus lines disclosure (CIC §1764.1), signed at application; broker fee disclosure if a fee is charged. Industrial-insured exemption **does not apply** (18 < 25). | Product → PLACED_IN Market(non-admitted, CA) → TRIGGERS Disclosure → EXEMPT_WHEN Rule, evaluated against Client.employees |
| CQ4 | Which locations does the client operate at that the policy doesn't cover? | The Vernon yard (leased last month). | Client → OPERATES_AT Locations minus Policy → COVERS Locations |
| CQ5 | What changed on this account since the underwriting file was written? | Design work now done in-house (file said none). New location in Vernon. | UnderwritingFacts with as_of vs. current Client facts; diff |
| CQ6 | Does Reyes's GL cover design work she does in-house? | **No.** Professional services exclusion. The product that does is Contractors Professional Liability, market non-admitted. | Coverage → EXCLUDES Exposure; Exposure → ADDRESSED_BY Product → PLACED_IN Market |
| CQ7 | Can a certificate be issued today showing completed-ops AI for the property manager? | **No.** Human-only action, and CQ1 says the form isn't there. Route to endorsement request. | CQ1 plus the certificate rule (Rule node) |
| CQ8 | If the client's home state were Texas, which disclosure replaces the D-1? | Texas surplus lines notice per TIC §981 (illustrative wording in the demo, labeled). Same call flow, different Disclosure node. | Market → TRIGGERS Disclosure scoped by State=TX. *Stretch; a later phase.* |

CQ1 through CQ7 must pass in the first phase. CQ8 proves the layer earned its keep and waits for a later phase.

## How each approach scores
| | A curated | B GraphRAG | C hybrid |
|---|---|---|---|
| Traceable path on every answer | Yes | Only if the extraction happened to make the edge | Yes, on the curated edges; RAG citations for text |
| Time to add a new carrier's form | Hours of hand modeling | Minutes | Minutes to propose, one human approval to accept |
| Who's liable when it's wrong | The modeler | Nobody you can name | The approver, by design |
| Fit for a regulated call | Good, slow | Fast, not defensible | Good enough, extensible |

The prototype shows C working and shows the approval queue (the review screen) so the tradeoff is visible on screen rather than claimed on a slide.

## Assumptions, stated
- The AMS exposes the policy, the attached forms, and the underwriting file as structured data. In the demo it's YAML; in production it's an API or a nightly export.
- ISO form numbers are stable public identifiers. Carrier proprietary forms would need their own nodes.
- One home state in the first phase (California). Multi-state is a scoping of edges by `State`, which the schema already carries.
- Statutory wording in the demo is quoted from public sources and labeled with its citation. Legal owns the words; the AI never edits them.
