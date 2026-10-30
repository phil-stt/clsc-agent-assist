# Work order 001: the core call, end to end

*2026-10-29. The contract for the first build. It lives in the repo so it travels with the code.*

## What we're building
An AI co-pilot for a commercial lines account manager on a live service call. The demo is one scripted eleven-minute call (Marisol Reyes, Reyes Design Build, calling Pacific Crest Insurance Services about a certificate) with the co-pilot panel beside the transcript. It has to change the outcome of the call on screen, with a graph behind every grounded answer.

Read `docs/design-brief.md` first. The scenario, the sample data, the three compliance beats, the certificate rule, and the human-in-the-loop table are all there and they're the spec. Then `docs/knowledge-layer.md` for the schema and the competency questions.

Serves: the working prototype in `docs/design-brief.md` ("What this project covers", item 3, parts a through d) and its knowledge layer section.

## Repo and hygiene
- Path: this repository. Phil creates the GitHub remote, private. He flips it public later; build to the public tier from commit one.
- Public tier means: no references to private working notes, internal tooling or the people this was built for, anywhere in the tree or in commit messages. No real policyholder, client, carrier, or call data. Every synthetic record labeled synthetic, in the README and in the data directory. MIT license. `.gitignore` excludes `.env` and outputs. Pinned dependencies.
- One command to run locally (`make dev` or `uv run ...`), one to test. A reader should clone and see the call playing inside ten minutes.
- Claude API from the backend only, key from `.env`. Phil's key, Phil's spend; keep calls cheap (one model call per beat, cached where the transcript is deterministic).

## Stack
FastAPI, Jinja2 templates with HTMX for the live panel, SQLite for state, NetworkX for the graph (seeded from YAML under `knowledge/`, persisted as JSON). No React. Tailwind via CDN is fine. If something here fights you, pick the faster thing and tell me.

## The knowledge layer (approach C)
Build it as `knowledge/`:
- `schema.yaml`: the entity types and edges from `docs/knowledge-layer.md`. Edges flagged `requires_approval: true` where they carry compliance meaning.
- `seed/`: curated YAML for the demo world. Agency, client, two locations, the three policies with attached forms, the product library (CGL, Contractors Pro Liability, Cyber, HNOA, Umbrella) with NAICS ranges, revenue bands, market, disclosures triggered. The underwriting file with `as_of` dates.
- `docs/`: synthetic long-form text. One short markdown stand-in per ISO form (CG 20 10, CG 20 33, CG 20 37, CG 20 01, CG 24 04), the product sheets, and the statute excerpts (CIC §1764.1 D-1 wording quoted and cited; CIC §1623 broker fee; a certificate-of-insurance statute summary). These are the RAG corpus.
- `disclosures/`: the verbatim texts the UI surfaces. `ca-recorded-line.md` (Legal's approved greeting, fictional), `ca-d1.md`, `ca-broker-fee.md`. Each carries its citation and an `owner: compliance` line. **The app never generates or edits these. It reads them.**
- `extract.py`: Claude reads `knowledge/docs/` and proposes edges against the schema into `proposed_edges.json`. In WO-001 this just needs to run and produce a queue; the approval UI is WO-002. Seed the graph from curated YAML so the demo doesn't depend on extraction.
- `cq/`: competency questions CQ1 through CQ7 as pytest. Each returns the answer and the path (node and edge ids). A test fails without a path.

## The call (the demo)
`data/call.yaml`: the scripted transcript, 10 to 12 beats, speaker-tagged, with timestamps. The UI plays it (auto-advance with a pause/step control) so Phil can present it or let it run. Label it plainly: "Simulated call. Scripted transcript stands in for live speech-to-text."

Beats, and what the panel must do at each:
1. **Greeting.** Recorded-line notice surfaced verbatim (CA two-party consent). Agent marks "delivered." If the agent advances the call without marking it, an amber nudge.
2. **Identify.** Account card loads: Reyes Design Build, NAICS 236220, 18 employees, $4.2M, home state CA, policies in force with carriers and limits.
3. **"I need a COI by Monday, they want AI ongoing and completed ops, primary and noncontributory, waiver of subrogation."** Call type detected: certificate request. The three contract requirements parsed into a checklist.
4. **Forms read.** Panel shows the forms actually attached to the GL (CG 20 33, CG 24 04) and matches them to the checklist. Ongoing ops: satisfied. Waiver: satisfied if scheduled. **Completed ops: not on the policy. Primary and noncontributory: not on the policy.** This is CQ1 and CQ2 on screen, with "show path" expanding the graph walk.
5. **The certificate block.** The "Issue certificate" action is disabled with the reason, and "Start endorsement request (CG 20 37, CG 20 01)" is offered instead. Suggested words for the agent to say honestly to Marisol. This is part (b) of the prototype in `docs/design-brief.md`: gap caught in-flow before a certificate goes out.
6. **"Oh, and we leased a yard in Vernon last month."** Location detected, not on the policy (CQ4). Endorsement queued: add location. Underwriting diff starts accumulating (CQ5).
7. **"We've started doing some of the design in-house now."** Exposure detected: professional services, excluded by the GL (CQ6). Product recommended: Contractors Professional Liability. Market: non-admitted. Agent confirms or dismisses (AI recommends, human confirms).
8. **Agent moves to quote.** Disclosures surface at this beat, verbatim with citations: D-1 (CIC §1764.1) and the broker fee disclosure. Industrial-insured check shown explicitly: 18 employees, threshold 25, exemption does not apply (CQ3). Agent marks each "delivered" or "sent for signature."
9. **The skip.** If the agent clicks "Request quote" before marking the D-1 delivered: amber block, "D-1 not yet delivered," with the text right there. This is part (c) of the prototype in `docs/design-brief.md`. Make it unmissable in the demo.
10. **Decline path.** Marisol says "let me think about it." Panel notes: exposure raised, product recommended, disclosure status, follow-up date.
11. **Wrap.** Three drafts, each in a review state (blue) until the agent accepts (green): activity note for the AMS, endorsement request to Westbrook Mutual (CG 20 37, CG 20 01, add Vernon location), follow-up email to Marisol. Nothing is "sent"; the demo stops at accepted drafts. Part (d).

## Human-in-the-loop, enforced in the UI
Use the table in `docs/design-brief.md` ("Where AI decides, recommends, or hands off") literally. Three visual states: **blue** is the AI proposing, **green** is a human decision, **amber** is a block or a nudge. Human-only actions (issue certificate, bind, quote, deliver disclosure, agree a fee, select the market) are either disabled with a reason or require an explicit agent click that gets logged. Keep a visible event log so the "guided text equals graded text" stretch has somewhere to read from later.

## Out of scope for WO-001
Audio or speech-to-text. Real AMS or carrier integrations. The extraction approval UI (WO-002). Second state (WO-004). Call scoring (WO-004). The deck and write-ups (WO-003, mine). Don't build any of it; mention it in the README roadmap.

## Acceptance criteria
1. `pytest` green, CQ1 through CQ7 passing with a path on each.
2. The call plays end to end; beats 5, 9 and 11 each do what's written above.
3. Disclosure text on screen is byte-identical to the file in `knowledge/disclosures/` and shows its citation.
4. No certificate can be produced from the UI showing completed-ops AI. Try to; it has to refuse with the reason.
5. `extract.py` runs and writes a non-empty `proposed_edges.json`.
6. README: synthetic data statement at the top, how to run, the HIL table, the roadmap, and "what's simulated."
7. Repo passes a grep for the public-tier scrub list and a secrets scan.

## What I need back, and when
- **End of Day 1:** graph seeded, CQ1 to CQ7 passing (paste the counts), beats 1 to 5 working, 3 screenshots (account card, the forms match with the gap, the certificate block).
- **End of Day 2:** full call, the skip nudge, the wrap drafts, README, one-command run, green tests. 3 more screenshots (the D-1 beat, the amber skip block, the wrap). A short note on anything you'd do differently.
- **Any scope cut the moment you make it**, with what it costs the demo.

Phil creates the remote and clicks every push and spend.

## Data rule
Synthetic only. Fictional agency, fictional client, fictional carriers, fictional calls. Statutory text may be quoted from public sources, labeled with its citation. Nothing real about any policyholder, client, carrier or employer, anywhere.
