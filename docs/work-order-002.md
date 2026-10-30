# Work order 002: the approval screen, and publish prep

*2026-10-30. One-day sprint.*

## What we're building
The other half of the hybrid, on screen. `extract.py` already proposes 32 edges with evidence quotes and match flags into `knowledge/proposed_edges.json`. Nothing enters the graph until a person approves it. WO-002 makes that person's screen, so "a human approves the edge" is something a reader can watch instead of a claim on a slide. Then the repo gets its last touches before it goes public.

Serves: the knowledge-architecture argument (the key tradeoff in the presentation) and Phase 2 of the roadmap.

The drift card at beat 6 is accepted as shipped. No change in this work order.

## The approval screen (`/review`)
- Lists every proposal in `proposed_edges.json`, oldest first, grouped by source document. Each row: proposed edge (from, relation, to), the evidence quote, the schema check result, the evidence-found check, and the match flag (matches curated edge X / new / conflicts with X).
- Three actions per proposal, each the reviewer's click, logged with who and when: **Approve** (enters the graph), **Reject** (recorded, never enters), **Merge** (for a proposal that restates an existing edge at a different level, like the two `MANDATES` rows restating `TRIGGERS`: pick which shape stays, the other is recorded as merged). Edit before approve is fine if cheap; otherwise reject and re-propose.
- Only edges flagged `requires_approval` in the schema need a human. Proposals on plain data edges may auto-approve with a visible "auto" tag, so the screen shows the line between the two. Count on screen: how many waited for a person.
- Approved edges are written to the graph with a provenance record (proposal id, document, quote, approver, timestamp) and the graph is rebuilt. The call UI's "show path" should display provenance on an edge that came in this way, so an answer can be traced to the document and the approver.
- Approvals persist in `knowledge/approvals.json` (append-only). `make graph` applies them on top of the curated seed, so a fresh clone with the file reproduces the reviewed graph.
- Same three colors: blue proposed, green approved, amber conflict or rejected.

## Tests
- A rejected proposal never appears in the graph (build, query, assert absent).
- An approved proposal appears with its provenance, and a CQ that walks it returns the provenance in the path.
- The two `MANDATES` proposals: merging one into `TRIGGERS` leaves exactly one edge of that meaning, not two.
- A `requires_approval` edge can't enter the graph by any route but the screen (no auto path).

## Publish prep (same sprint)
- README: add a "Presentation" line linking the deck (a placeholder `[deck link]` until the share link exists), and a "Review screen" paragraph under "How it's built."
- README roadmap: Phase 2's first half is now built; reword so Phase 2 reads "grade the call from the same graph."
- Run the scrub and the secrets scan on the full history one more time, and paste the output in the report.
- Confirm `make dev` from a fresh clone still plays all 11 beats with no key, and `/review` loads with the 32 proposals.
- Anything in the tree that still reads like an assignment artifact: list it for review.

## Acceptance criteria
1. `/review` lists all 32 proposals with evidence and match flags; approve, reject and merge each work and are logged.
2. The four tests above pass; whole suite green.
3. "Show path" on an approved-edge answer shows document, quote and approver.
4. Fresh clone: `make dev`, 11 beats, `/review` loads. No key needed.
5. Scrub and secrets scan clean on the full history; output in the report.
6. README updated as above.

## What I need back
- One report at the end: screenshot of `/review` with the `MANDATES` merge visible, screenshot of a path with provenance, test counts, scrub output, and the list from the last publish-prep bullet.
- Any scope cut the moment you make it.

## Data rule
Unchanged. Synthetic only. Public tier from every commit.
