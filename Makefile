PYTHON ?= python3
VERSION ?= 3.0.4

.PHONY: help check test compile doctor postgres-test release-check shell-check run worker scheduler lint-security docker-build

help:
	@echo "zWorkforce Control Plane - Available Makefile Targets:"
	@echo "  make check          - Run all test, doctor, release-check, shell-check, and lint-security gates"
	@echo "  make compile        - Compile Python bytecode across zworkforce, tests, and scripts"
	@echo "  make test           - Run full Python unit test discovery suite"
	@echo "  make doctor         - Run zWorkforce system doctor health check"
	@echo "  make postgres-test  - Run PostgreSQL integration tests (requires ZWORKFORCE_TEST_POSTGRES_URL)"
	@echo "  make release-check  - Verify release artifacts and metadata integrity"
	@echo "  make shell-check    - Syntax check bash scripts and frontend JS"
	@echo "  make lint-security  - Verify no shell=True or exposed static provider credentials"
	@echo "  make run            - Start local zWorkforce API server"
	@echo "  make worker         - Start local background worker daemon"
	@echo "  make scheduler      - Run one-shot scheduler tick"
	@echo "  make docker-build   - Build production Docker image"

check: test doctor release-check shell-check lint-security

compile:
	$(PYTHON) -m compileall -q zworkforce tests scripts

test: compile
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -v

doctor:
	PYTHONPATH=. $(PYTHON) -m zworkforce doctor

postgres-test:
	@test -n "$${ZWORKFORCE_TEST_POSTGRES_URL:-}" || (echo "set ZWORKFORCE_TEST_POSTGRES_URL to a real PostgreSQL service" >&2; exit 2)
	PYTHONPATH=. $(PYTHON) -m unittest tests.test_v3_postgres -v

release-check:
	$(PYTHON) scripts/verify_release.py --expected $(VERSION)

shell-check:
	bash -n scripts/*.sh
	node --check zworkforce/static/app.js

run:
	python -m zworkforce serve

worker:
	python -m zworkforce worker

scheduler:
	python -m zworkforce scheduler --once

lint-security:
	! grep -R --line-number --include="*.py" "shell=True" zworkforce
	! grep -R --line-number -E "API_KEY|provider_api_key|Authorization: Bearer" zworkforce/static

sec-scan: lint-security
	@echo "Static security checks passed: zero shell=True and zero static credentials."

docker-build:
	docker build --build-arg VERSION=$(VERSION) -t zworkforce:$(VERSION) .
