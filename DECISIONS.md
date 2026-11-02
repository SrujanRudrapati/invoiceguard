# Decisions
0:00 | Start | CLAUDE.md committed
~0:10 | Load ANTHROPIC_API_KEY via python-dotenv in config.py; key read lazily | export in shell | user-approved; offline code (data, tests) never needs the key | `make test` runs without a key
~0:10 | Track runs/history.jsonl, ignore rest of runs/ | ignore runs/ entirely | evals page and commit messages need the history | .gitignore
~0:10 | Labels record printed values, even when the math is wrong | label the "correct" totals | extraction is scored on reading; rules catch bad math, so the two stay separable | test_each_arithmetic_error_breaks_exactly_one_check
~0:10 | 3 distinct arithmetic defects: line sum, total, one line amount | same defect x3 | each exercises a different rule | same test
~0:10 | Non-invoice labels carry only doc_type | label quote/shipping fields | field_acc is scoped to invoices; reject accuracy reported separately | test_non_invoices_carry_only_doc_type
~0:10 | Money as Decimal, serialized as strings in JSONL | float | exact sums in rule checks | schema.py
~0:10 | Messy docs: abbreviated labels, "03 Nov 2026" dates, currency symbols, Amt Due also in header | messy = visual noise only | harder text, same truth | data/docs
~0:10 | Fixed seed + reportlab invariant=1 | random per run | byte-identical PDFs across reruns | test_generation_is_deterministic
0:XX | Phase 1 done | 24 docs, 24 labels
~0:10 | Phase 1 done | 24 docs, 24 labels
0:27 | Phase 2 done | baseline table printed
~0:27 | Extracted[T] = {value, evidence, evidence_boxes} for scalars; line items plain | evidence per line item | spec; keeps LLM output small | schema.py
~0:27 | Ingest via page.get_textmap(): text + 1 box per char | re-derive boxes from words | identical to extract_text(), so regex/LLM spans map straight to boxes | test_text_and_boxes_align_on_every_generated_doc
~0:27 | Grounding = normalized-exact quote found in text; value-in-quote not checked yet | also check value appears in quote | as specified; note an LLM could quote "Total: 6,447.00" and answer 0 and still be grounded | test_grounding.py
~0:27 | Review recall denominator = gold route review (6); rejects scored as reject_acc | all docs that should not be approved (8) | follows earlier answer 4; avoids counting non-invoices twice | test_review_recall_counts_review_docs_not_auto_approved
~0:27 | Phase 2 route: not_invoice -> reject, missing required field -> review, else approve; rules plug in later | wait for rules.py | eval needs a route now | baseline confusion: review 2/6 caught
~0:27 | Scoring is pure functions in eval/scoring.py; each file processed once across label sets | metrics inline in run_eval | unit-testable; no double API cost later | test_scoring.py
~0:27 | history git_sha gets "-dirty" when the tree has changes | bare sha | eval runs before the commit, so bare sha would lie | run_eval.git_sha
~0:30 | Baseline was tuned on all templates; restricted it so the messy layouts are held out (standard labels, the 3 standard date formats, no currency symbols) | keep tuned regex | regex was written after reading messy docs, so it was scored on its own training data | before: field_acc 1.000, line_item_acc 1.000, doc_exact 1.000, auto_approve 0.833, review 2/6; after: field_acc 0.879, line_item_acc 0.897, doc_exact 0.833, auto_approve 0.667, review 2/6
0:35 | v0 done | review recall 2/6, field_acc 0.879, auto-approve 0.667
~0:35 | Skills: claude-api (Phase 3: SDK shapes, price check; model IDs from config.py, no thinking) and frontend-design (Phase 6) | webapp-testing (adds playwright dep; Playwright tools already connected), context7 (sends queries to a third-party service), tdd-workflow (80% coverage + E2E mandate, heavier than needed), /fastapi-review (checks auth/CORS/rate limits CLAUDE.md excludes), eval-harness (evaluates coding sessions, not product evals), react-pdf skills (cover @react-pdf/renderer, not the react-pdf viewer), framer-motion (community, generic), pdf, ai-regression-testing (Vitest/Next.js) | both already available, no install; official sources; each maps to one phase | skill-scout search, SKILL.md files read
