.PHONY: install lint test run docker-up docker-down smoke

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check src tests

test:
	pytest -q

run:
	uvicorn ztrader_intel.api:app --host 0.0.0.0 --port $${ZTRADER_INTEL_PORT:-8218}

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

smoke:
	curl -fsS http://127.0.0.1:$${ZTRADER_INTEL_PORT:-8218}/health
