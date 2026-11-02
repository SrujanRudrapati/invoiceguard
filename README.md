# InvoiceGuard

Extracts invoice fields with evidence, validates them with business rules, escalates
Haiku -> Sonnet only on extraction failure, and routes each document to approve / review / reject.

```
cp .env.example .env   # add ANTHROPIC_API_KEY
make setup             # uv sync (+ npm install once web/ exists)
make data              # 24 synthetic PDFs + data/labels.jsonl (fixed seed)
make test
```

Evals: `make eval SYSTEM=baseline|haiku|sonnet|cascade SET=main|hard TAG=vX`, then
`make compare TAG=vX` for the side-by-side table and `make analyze` for categorized errors.

Review app: `make demo` resets the SQLite DB, processes data/docs with the cascade
(`DEMO_SYSTEM=baseline` runs offline for $0), then starts the API on :8000 and the app on
http://localhost:5173. Keys: J/K fields, Enter edit, Esc cancel, A approve, S save and approve,
R reject, Up/Down documents, ? shortcuts. Save and approve with edits appends the corrected
labels to data/labels_reviewed.jsonl (source "reviewer"); `make eval` reports them separately.
See CLAUDE.md for the plan and DECISIONS.md for choices made.
