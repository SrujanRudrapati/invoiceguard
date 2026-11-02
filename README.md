# InvoiceGuard

Invoice extraction with evidence, business-rule checks, a Haiku → Sonnet cascade, and a
keyboard-driven review desk where every correction becomes a test case.

On 24 labeled invoices it catches 6/6 bad invoices before approval (regex alone: 2/6),
auto-approves 15 of 16 (94%) good ones, and marks zero wrong values as verified, at $0.0005/doc.
Sonnet alone costs ~20x more and changed no routing decision, so the cascade escalates rarely.
Built in about 4 hours; tags v0–v4 show each step.

![Review desk: selected field linked to its evidence](docs/review-desk.png)

## Run it
    make setup && cp .env.example .env    # add ANTHROPIC_API_KEY
    make data && make eval SYSTEM=cascade
    make demo                              # review desk at http://localhost:5173
    make test
No key? SYSTEM=baseline and DEMO_SYSTEM=baseline run offline.

## Why this problem
TODO (Srujan): 2-3 sentences. The costly error in accounts payable is approving a wrong
invoice, so I optimized for catching bad ones first and automating clean ones second.

## How it works
ingest (text + char boxes) → Haiku extraction (schema, quote per field) → grounding
(quote exists AND value matches it) → escalate to Sonnet only if a required field is
ungrounded or extraction fails → business rules → route approve / review / reject
→ review desk → audit log + reviewer cases appended to the eval set

## Results
Main set (24 docs) and hard set (6 docs), from make compare TAG=v3.1:

Main set (24 docs)

| system | field_acc | line_item_acc | doc_exact | review_recall | reject_acc | auto_approve | verified_wrong | escalation_rate | p50_ms | usd_per_doc |
|---|---|---|---|---|---|---|---|---|---|---|
| regex (baseline) | 0.879 | 0.897 | 0.833 | 1.000 | 1.000 | 0.458 | 0 | 0.000000 | 6.453 | 0.000000 |
| haiku | 0.985 | 1.000 | 0.917 | 1.000 | 1.000 | 0.625 | 0 | 0.000000 | 2992.029 | 0.000493 |
| sonnet | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.625 | 0 | 0.000000 | 4244.591 | 0.009983 |
| cascade | 0.985 | 1.000 | 0.917 | 1.000 | 1.000 | 0.625 | 0 | 0.000000 | 2777.624 | 0.000497 |

Hard set (6 docs)

| system | field_acc | line_item_acc | doc_exact | review_recall | reject_acc | auto_approve | verified_wrong | escalation_rate | p50_ms | usd_per_doc |
|---|---|---|---|---|---|---|---|---|---|---|
| regex (baseline) | 0.815 | 0.853 | 0.333 | 1.000 | n/a | 0.667 | 3 | 0.000000 | 6.100 | 0.000000 |
| haiku | 1.000 | 1.000 | 1.000 | 1.000 | n/a | 0.833 | 0 | 0.000000 | 2320.591 | 0.000570 |
| sonnet | 1.000 | 1.000 | 1.000 | 1.000 | n/a | 0.667 | 0 | 0.000000 | 4081.045 | 0.011 |
| cascade | 1.000 | 1.000 | 1.000 | 1.000 | n/a | 0.833 | 0 | 0.167 | 2372.005 | 0.002032 |

auto_approve is the share of all documents approved; review_recall is strict (a review-worthy
document counts only if routed to review). Full columns: `make compare TAG=v3.1`.

Reviewer set (corrections from the app): n=1, field_acc 0.778 (cascade, TAG=v4; $0.000496/doc on the main set in that run)

![Evals: cost vs review recall](docs/evals.png)

## What error analysis found
- Rules, not the model, catch bad invoices: regex + rules also reaches 6/6. Haiku's value
  is field accuracy (0.879 → 0.985) and auto-approval on messy layouts.
- Slash dates like 10/05/2026 were misread and still marked verified. Fix: resolve date
  order per document; if every date is ambiguous, send to review without escalating,
  because a stronger model can't resolve ambiguity that's in the document.
  verified_wrong 3 → 0.
- My first regex baseline was tuned on all templates; I restricted it so messy layouts
  are held out.

## How I worked
| Tag | Step | Key number |
|---|---|---|
| v0 | Eval harness + regex baseline, messy layouts held out | review recall 2/6, field_acc 0.879 |
| v1 | Haiku extraction + grounding + rules + routing | review recall 2/6 → 6/6 (regex + rules also 6/6), field_acc 0.879 → 0.985, $0.00049/doc |
| v2 | Error analysis → per-document date order | verified_wrong 3 → 0 |
| v3 | Cascade + Sonnet reference + 6-doc hard set | cascade $0.000492 vs Sonnet $0.009939/doc, 0/24 escalated |
| v3.1 | EU decimals per document, strict review recall, credit notes as billing docs | hard set: cascade field_acc 0.870 → 1.000, review recall 1/1 |
| v4 | Review app + corrections become eval cases | reviewer set n=1; cascade recall 1.000, $0.000496/doc |

CLAUDE.md shows how I directed Claude Code. DECISIONS.md logs each choice with time.

## Decisions and trade-offs
| Decision | Rejected | Why |
|---|---|---|
| Haiku first, Sonnet on failure | Sonnet for everything | ~20x cost, no routing change |
| Quote per field + value consistency | Trust model output | Catches values the quote doesn't support |
| Arithmetic in code | Ask the model | Exact, testable, free |
| Ambiguous dates go to review, no escalation | Escalate | Ambiguity is in the document |
| Kept doc_015's gold label | Relabel to fit the policy | Don't edit test data to improve scores |
| FastAPI + React | Streamlit | Keyboard flow and evidence linking need a real front end |

## Honest limits
- 24 + 6 synthetic documents, labels written by me.
- The credit-note prompt change was made after seeing that failure (logged).
- p50 latency about 3 s per document.

## What I left out (4-hour cap)
- OCR for scanned images
- A real-invoice eval set
- Vendor matching and duplicate detection
- Auth, roles, deployment

## Next three fixes
1. Grounding drops the minus sign on credit-note amounts (wastes one Sonnet call).
2. Two-line vendor names get quoted partially; match quotes across line breaks.
3. Tune TODO (Srujan): the template was cut off after "Tune".
