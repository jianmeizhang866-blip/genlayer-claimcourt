# ClaimCourt — web-grounded adjudication primitives for GenLayer

Three small Intelligent Contracts that together show what "does it actually need
consensus?" means in practice: a web-grounded adjudicator, a stable-field extraction
oracle, and a deterministic settlement gate that consumes the verdict.

Written against `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`
(the SDK pinned by the current Studio). Deployed and exercised on StudioNet.

## Why this exists

Every GenLayer demo ends up needing the same three things, and each one fails in a
different way if you build it naively:

| Problem | Naive attempt | Why it breaks | What this repo does |
|---|---|---|---|
| Decide a plain-English claim from a cited source | ask an LLM, store the string | validators get different prose, consensus never converges | judge inside the non-deterministic block, return a **structured** verdict, validate the *shape* |
| Feed an oracle from a live page | return the whole page | counts, ads and timestamps differ between validator requests | caller names the **fields**; only those fields leave the non-deterministic block |
| Pay out on a verdict | put the LLM call inside the payout path | money logic becomes non-deterministic and unauditable | adjudication is stored by id; settlement stays **fully deterministic** and consumes the id |

## Contracts

### `claim_court.py` — ClaimCourt

`resolve(claim, source_url)` renders the page (`gl.nondet.web.render`, text mode,
3s settle wait), asks the model for
`{"verdict": "TRUE"|"FALSE"|"UNCLEAR", "quote": "..."}` with
`exec_prompt(response_format="json")`, and runs it through
`gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`. The validator rejects anything that
is not a dict with an allowed verdict and a `<= 200` char quote — it never compares LLM
prose to LLM prose, which is the failure mode `strict_eq` has on model output.

Storage is append-only: `claims / verdicts / evidence / sources` keyed by an
incrementing id. `get(claim_id)` returns the full record including the evidence quote
and the source URL, so the adjudication is auditable after the fact.

### `source_watch.py` — SourceWatch

`watch(watch_id, source_url, fields)` takes a comma-separated field list and returns
only those fields, each coerced to a short scalar string (absent → `NOT_FOUND`). The
validator requires every requested key to be present and `<= 120` chars. This is the
"extract stable fields" guidance turned into a reusable contract: cosmetic page changes
stop breaking consensus, while malformed extractions are still rejected. Rounds are
counted per `watch_id`, so a caller can poll and diff over time.

### `escrow_gate.py` — EscrowGate

Deterministic. `open_deal(deal_id, buyer, seller, amount, terms_url)` then
`settle(deal_id, verdict, evidence_ref_id)`. Only `OPEN` deals settle, only
`TRUE`/`FALSE` is accepted, and an evidence reference is mandatory — a rejected
settlement leaves the deal untouched so it can be retried with better evidence rather
than being bricked. `TRUE` names the seller as beneficiary, `FALSE` the buyer.
No value moves on StudioNet (the sandbox has no transfers); on a value-bearing network
the settlement branch would add `emit_transfer`, which is a one-line change because the
payout logic is already deterministic.

## Exercise it in 4 calls

1. Deploy `claim_court.py` (no constructor arguments).
2. `ClaimCourt.resolve("Bitcoin was created before 2010", "https://en.wikipedia.org/wiki/Bitcoin")`
   → `{"id": "1", "verdict": "TRUE"}`.
3. Deploy `source_watch.py` → `SourceWatch.watch("btc", "https://en.wikipedia.org/wiki/Bitcoin", "ticker,launch_year")`.
4. Deploy `escrow_gate.py` → `open_deal("d1", "buyer.eth", "seller.eth", 100, "https://example.com/terms")`
   then `settle("d1", "TRUE", "claimcourt:1")` → `paid_to` is the seller.

## Design notes

- No `float` anywhere near consensus-sensitive code; amounts are integers.
- Storage uses `TreeMap` only; non-deterministic blocks read nothing from storage —
  every value they need is a local parameter captured by the closure.
- Leader and validator functions are declared inside the write method and take no
  bound `self`, per GenVM's structural requirements.
- Verdict vocabulary is closed (`TRUE`/`FALSE`/`UNCLEAR`) so downstream contracts can
  branch on it without parsing model output.
