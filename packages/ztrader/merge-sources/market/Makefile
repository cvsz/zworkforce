.PHONY: install lint typecheck test api dev secret-scan audit docker-build ecc-import ecc-import-dry-run

install:
	python -m pip install -e '.[dev]'

lint:
	ruff check src tests

typecheck:
	mypy src

test:
	pytest

api:
	uvicorn zkbtrader.api:app --host 127.0.0.1 --port 8004 --reload

dev:
	docker compose up --build

secret-scan:
	bash scripts/secret-scan.sh

audit:
	bandit -q -r src
	pip-audit

docker-build:
	docker build -f Dockerfile.api -t zkbtrader-api:local .

ecc-import:
	bash scripts/ecc-import.sh

ecc-import-dry-run:
	DRY_RUN=1 bash scripts/ecc-import.sh
