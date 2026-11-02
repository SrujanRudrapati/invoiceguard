# InvoiceGuard

Extracts invoice fields with evidence, validates them with business rules, escalates
Haiku -> Sonnet only on extraction failure, and routes each document to approve / review / reject.

```
cp .env.example .env   # add ANTHROPIC_API_KEY
make setup             # uv sync (+ npm install once web/ exists)
make data              # 24 synthetic PDFs + data/labels.jsonl (fixed seed)
make test
```

Other targets: `eval`, `analyze`, `api`, `web`, `demo` (filled in by later phases).
See CLAUDE.md for the plan and DECISIONS.md for choices made.
