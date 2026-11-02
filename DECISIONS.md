# Decisions
0:00 | Start | CLAUDE.md committed
?:?? | Load ANTHROPIC_API_KEY via python-dotenv in config.py; key read lazily | export in shell | user-approved; offline code (data, tests) never needs the key | `make test` runs without a key
?:?? | Track runs/history.jsonl, ignore rest of runs/ | ignore runs/ entirely | evals page and commit messages need the history | .gitignore
?:?? | Labels record printed values, even when the math is wrong | label the "correct" totals | extraction is scored on reading; rules catch bad math, so the two stay separable | test_each_arithmetic_error_breaks_exactly_one_check
?:?? | 3 distinct arithmetic defects: line sum, total, one line amount | same defect x3 | each exercises a different rule | same test
?:?? | Non-invoice labels carry only doc_type | label quote/shipping fields | field_acc is scoped to invoices; reject accuracy reported separately | test_non_invoices_carry_only_doc_type
?:?? | Money as Decimal, serialized as strings in JSONL | float | exact sums in rule checks | schema.py
?:?? | Messy docs: abbreviated labels, "03 Nov 2026" dates, currency symbols, Amt Due also in header | messy = visual noise only | harder text, same truth | data/docs
?:?? | Fixed seed + reportlab invariant=1 | random per run | byte-identical PDFs across reruns | test_generation_is_deterministic
