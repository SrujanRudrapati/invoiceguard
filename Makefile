.PHONY: setup data eval analyze api web demo test lint

setup:
	uv sync
	@if [ -f web/package.json ]; then cd web && npm install; fi

data:
	uv run python scripts/make_synthetic.py

eval:
	uv run python eval/run_eval.py

analyze:
	uv run python eval/analyze.py

api:
	uv run uvicorn invoiceguard.api:app --reload --port 8000

web:
	cd web && npm run dev

demo:
	$(MAKE) -j2 api web

test:
	uv run pytest -q

lint:
	uv run ruff check .
