# Commercial lines agent assist

> **All data in this repository is synthetic.** The agency, the client, the carriers, the policies, the contract and the call are made up. Statute text is quoted from public sources and labeled with its citation. ISO form numbers are real public identifiers; the form texts here are short paraphrased stand-ins, not ISO wording.

An AI co-pilot for a commercial lines account manager on a live service call. One scripted eleven-minute call plays on the left. On the right, the co-pilot pulls the account, reads the endorsements actually attached to the policy, blocks a certificate the policy can't support, and surfaces the exact disclosure at the right beat. A knowledge graph sits behind every grounded answer, and each answer can show the path it walked.

The problem, the scenario and the evaluation criteria are in [`docs/use-case.md`](docs/use-case.md). The architecture decision and the competency questions are in [`docs/knowledge-layer.md`](docs/knowledge-layer.md). The build contract is in [`docs/work-order-001.md`](docs/work-order-001.md).

## Run it

Requires Python 3.12.

```bash
make dev     # creates .venv, installs pinned deps, builds the graph, serves http://localhost:8000
make test    # competency questions CQ1–CQ7 plus the UI's compliance checks
```

No API key is needed. Each beat's model response is recorded in `data/llm_cache/`; when a beat has no recording and no key is set, the beat's scripted detection is used and the panel says so. To record fresh responses, copy `.env.example` to `.env` and add a key.

## How it's built

- **`knowledge/`**: the curated schema (`schema.yaml`), the seed for the demo world (`seed/`), the long-form corpus (`docs/`), and the verbatim disclosures (`disclosures/`). `graph.py` builds a NetworkX graph and writes `graph.json`. `queries.py` answers the competency questions, and each answer returns its path. The tests in `cq/` fail without one.
- **`app/`**: FastAPI, Jinja2 and HTMX. `llm.py` is the only code that calls a model, and it only reads each beat for intent, contract requirements, locations and exposures. Forms matching, the certificate rule and disclosure selection are deterministic graph walks.
- **`data/call.yaml`**: the scripted call.

## Status

Work in progress. Beats 1 to 5 work: the recorded-line notice with its nudge, the account card, call-type detection, the forms match with the gap, and the certificate block. Beats 6 to 11, the wrap drafts, edge extraction and the full write-up are next.
