SYSTEM ?= baseline
SET ?= main
DEMO_SYSTEM ?= auto
TAG ?=

.PHONY: setup data eval compare analyze api web demo serve test lint

setup:
	uv sync
	@if [ -f web/package.json ]; then cd web && npm install; fi

data:
	uv run python scripts/make_synthetic.py
	uv run python scripts/make_hard.py

eval:
	uv run python eval/run_eval.py --system $(SYSTEM) --set $(SET) --tag "$(TAG)"

compare:
	uv run python eval/compare.py --tag "$(TAG)"

analyze:
	uv run python eval/analyze.py

api:
	uv run uvicorn invoiceguard.api:app --reload --port 8000

web:
	cd web && npm run dev

demo:
	uv run python -m invoiceguard.process --system $(DEMO_SYSTEM)
	$(MAKE) -j2 api web

serve:  # production mode: built web app at /, API at /api, one port
	cd web && npm run build
	uv run uvicorn invoiceguard.serve:create_app --factory --port $${PORT:-8000}

test:
	uv run pytest -q

lint:
	uv run ruff check .
