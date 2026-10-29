PYTHON ?= python3
PYTHON_VENV ?= .venv/bin/python
VERSION ?= 3.0.4
REPO_ROOT := $(shell pwd)

.PHONY: help check test compile doctor postgres-test release-check shell-check lint-security sec-scan \
	run worker scheduler docker-build vault-setup vault-status stage-f release-gate verify-release \
	git-status git-gpg-sign git-verify cloudflare-plan cloudflare-apply cloudflare-status \
	start stop restart status env-check secrets-check static-security full-validation ci-validation

# ==============================================================================
# zWorkforce Control Plane - Enterprise Makefile
# ==============================================================================

help:
	@echo "zWorkforce Control Plane - Available Makefile Targets (v$(VERSION))"
	@echo ""
	@echo "Core validation (AGENTS.md required):"
	@echo "  make compile        - Compile Python bytecode across zworkforce, tests, and scripts"
	@echo "  make test           - Run full Python unit test discovery (unittest, AGENTS.md required)"
	@echo "  make doctor         - Run zWorkforce system doctor health check"
	@echo "  make check          - Run all core gates: compile, test, doctor, release-check, shell-check, lint-security"
	@echo ""
	@echo "PostgreSQL integration:"
	@echo "  make postgres-test  - Run PostgreSQL integration tests (requires ZWORKFORCE_TEST_POSTGRES_URL)"
	@echo ""
	@echo "Release & governance:"
	@echo "  make release-check  - Verify release artifacts and metadata integrity"
	@echo "  make verify-release - Full release gate verification (ledger + external evidence)"
	@echo "  make git-status     - Show working tree and branch status"
	@echo "  make git-gpg-sign   - Verify GPG signing key is configured"
	@echo "  make git-verify     - Verify last commit is GPG-signed"
	@echo ""
	@echo "Security scanning:"
	@echo "  make shell-check    - Syntax check bash scripts and frontend JS"
	@echo "  make lint-security  - Verify no shell=True or exposed static provider credentials"
	@echo "  make sec-scan       - Combined shell-check + lint-security"
	@echo "  make secrets-check  - Verify no real secrets in committed files"
	@echo "  make env-check      - Validate environment configuration (no placeholder secrets)"
	@echo ""
	@echo "Vault & external gates:"
	@echo "  make vault-setup    - Initialize local Vault dev server and write placeholder secrets"
	@echo "  make vault-status   - Check Vault server health and secret paths"
	@echo "  make stage-f        - Run Stage F S3 artifact write/read + SHA-256 verification"
	@echo ""
	@echo "Cloudflare / Terraform:"
	@echo "  make cloudflare-plan - Create Terraform plan (review only, no apply)"
	@echo "  make cloudflare-apply - Apply approved Terraform plan (requires --approved-plan-sha256)"
	@echo "  make cloudflare-status - Show Cloudflare stack status"
	@echo ""
	@echo "Runtime:"
	@echo "  make start          - Start zWorkforce API server (port $(ZWF_PORT), PID file $(PID_FILE))"
	@echo "  make stop           - Stop zWorkforce API server"
	@echo "  make restart        - Restart zWorkforce API server"
	@echo "  make status         - Check zWorkforce API health"
	@echo "  make run            - Start local zWorkforce API server (foreground)"
	@echo "  make worker         - Start local background worker daemon"
	@echo "  make scheduler      - Run one-shot scheduler tick"
	@echo "  make docker-build   - Build production Docker image"
	@echo ""
	@echo "Full validation:"
	@echo "  make full-validation - Run compile, test, doctor, postgres-test (if URL set), sec-scan, env-check"
	@echo "  make ci-validation   - CI-equivalent validation (compile + test + doctor + sec-scan)"

# ------------------------------------------------------------------------------
# Core validation (AGENTS.md required)
# ------------------------------------------------------------------------------

check: compile test doctor release-check shell-check lint-security

compile:
	$(PYTHON) -m compileall -q zworkforce tests scripts

test: compile
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -v

doctor:
	PYTHONPATH=. $(PYTHON) -m zworkforce doctor

# ------------------------------------------------------------------------------
# PostgreSQL integration
# ------------------------------------------------------------------------------

postgres-test:
	@test -n "$${ZWORKFORCE_TEST_POSTGRES_URL:-}" || (echo "set ZWORKFORCE_TEST_POSTGRES_URL to a real PostgreSQL service" >&2; exit 2)
	PYTHONPATH=. $(PYTHON) -m unittest tests.test_v3_postgres -v

# ------------------------------------------------------------------------------
# Release & governance
# ------------------------------------------------------------------------------

release-check:
	$(PYTHON) scripts/verify_release.py --expected $(VERSION)

verify-release: compile test doctor release-check shell-check lint-security
	@echo "=== Release gate verification ==="
	@test -f docs/PRODUCTION-EVIDENCE.md || (echo "docs/PRODUCTION-EVIDENCE.md is missing" >&2; exit 1)
	@grep -q "PASS" docs/PRODUCTION-EVIDENCE.md || (echo "No PASS evidence found in PRODUCTION-EVIDENCE.md" >&2; exit 1)
	@echo "Release gate verification complete."

# ------------------------------------------------------------------------------
# Git & GPG
# ------------------------------------------------------------------------------

git-status:
	@git status --short
	@echo "---"
	@git log --oneline -5

git-gpg-sign:
	@test -n "$$(git config user.signingkey)" || (echo "GPG signing key not configured. Run: git config user.signingkey <key-id>" >&2; exit 1)
	@echo "GPG signing key: $$(git config user.signingkey)"
	@gpg --list-secret-keys --keyid-format LONG

git-verify:
	@git log -1 --show-signature --format="%GK %G? %gD" | grep -q "G" || (echo "Last commit is not GPG-signed" >&2; exit 1)
	@echo "Last commit is GPG-signed: OK"

# ------------------------------------------------------------------------------
# Security scanning
# ------------------------------------------------------------------------------

shell-check:
	bash -n scripts/*.sh
	node --check zworkforce/static/app.js

lint-security:
	! grep -R --line-number --include="*.py" "shell=True" zworkforce
	! grep -R --line-number -E "API_KEY|provider_api_key|Authorization: Bearer" zworkforce/static

sec-scan: lint-security
	@echo "Static security checks passed: zero shell=True and zero static credentials."

secrets-check:
	! grep -R --line-number -E "sk-[A-Za-z0-9]{20,}|sb_secret_[A-Za-z0-9]{20,}|iydot0Ut8ofu|@@@Zz112233" zworkforce tests scripts docs --include="*.py" --include="*.sh" --include="*.md" --include="*.yml" --include="*.yaml" --include="*.json" || (echo "Potential secrets found in committed files" >&2; exit 1)
	@echo "No exposed secrets found in committed files."

env-check:
	@test -f .env.release.example || (echo ".env.release.example is missing" >&2; exit 1)
	@grep -q "vault://\|file://\|aws-sm://" .env.release.example || (echo ".env.release.example does not use secret references" >&2; exit 1)
	@echo "Environment configuration uses secret references: OK"

# ------------------------------------------------------------------------------
# Vault & external gates
# ------------------------------------------------------------------------------

VAULT_ADDR ?= http://127.0.0.1:8200
VAULT_TOKEN ?= zworkforce-local-token
VAULT_BIN ?= $(HOME)/bin/vault

vault-setup:
	@command -v $(VAULT_BIN) >/dev/null 2>&1 || (echo "Vault CLI not found at $(VAULT_BIN). Install HashiCorp Vault first." >&2; exit 1)
	@pgrep -f "vault server -dev" >/dev/null 2>&1 || (echo "Starting Vault dev server..."; nohup $(VAULT_BIN) server -dev -dev-root-token-id="$(VAULT_TOKEN)" -dev-listen-address="0.0.0.0:8200" > /tmp/vault-dev.log 2>&1 & sleep 3;)
	@export VAULT_ADDR="$(VAULT_ADDR)" VAULT_TOKEN="$(VAULT_TOKEN)"; \
	$(VAULT_BIN) status >/dev/null 2>&1 || (echo "Vault server is not reachable at $(VAULT_ADDR)" >&2; exit 1)
	@echo "Vault server is running at $(VAULT_ADDR)"
	@echo "Writing placeholder secrets to Vault paths referenced in .env.release..."
	$(VAULT_BIN) kv put secret/data/zworkforce/build \
		sudo_pass_prod='PLACEHOLDER_REPLACE_ME' \
		sudo_pass_core='PLACEHOLDER_REPLACE_ME' \
		root_pass_wsl2='PLACEHOLDER_REPLACE_ME' \
		gpg_passphrase='PLACEHOLDER_REPLACE_ME'
	$(VAULT_BIN) kv put secret/data/zworkforce/postgres-production \
		password='PLACEHOLDER_REPLACE_ME'
	$(VAULT_BIN) kv put secret/data/zworkforce/supabase-s3 \
		access_key='PLACEHOLDER_REPLACE_ME' \
		secret_key='PLACEHOLDER_REPLACE_ME'
	$(VAULT_BIN) kv put secret/data/zworkforce/supabase-database \
		password='PLACEHOLDER_REPLACE_ME'
	$(VAULT_BIN) kv put secret/data/zworkforce/supabase \
		publishable_key='PLACEHOLDER_REPLACE_ME' \
		secret_key='PLACEHOLDER_REPLACE_ME' \
		next_public_publishable_key='PLACEHOLDER_REPLACE_ME' \
		access_key='PLACEHOLDER_REPLACE_ME' \
		access_secret_key='PLACEHOLDER_REPLACE_ME' \
		active_shared_keys='PLACEHOLDER_REPLACE_ME' \
		standby_keys='PLACEHOLDER_REPLACE_ME'
	@echo "Vault secrets written (all placeholders — replace with real credentials)."

vault-status:
	@export VAULT_ADDR="$(VAULT_ADDR)" VAULT_TOKEN="$(VAULT_TOKEN)"; \
	$(VAULT_BIN) status 2>/dev/null || (echo "Vault server is not reachable" >&2; exit 1)
	@echo "---"
	@$(VAULT_BIN) kv list secret/data/zworkforce/ 2>/dev/null || (echo "No secret paths found" >&2; exit 1)

stage-f:
	@test -n "$${SUPABASE_S3_ACCESS_KEY:-}" || (echo "set SUPABASE_S3_ACCESS_KEY and SUPABASE_S3_SECRET_KEY env vars" >&2; exit 2)
	@test -n "$${SUPABASE_S3_SECRET_KEY:-}" || (echo "set SUPABASE_S3_ACCESS_KEY and SUPABASE_S3_SECRET_KEY env vars" >&2; exit 2)
	export VAULT_ADDR="$(VAULT_ADDR)" VAULT_TOKEN="$(VAULT_TOKEN)" VAULT_BIN="$(VAULT_BIN)"; \
	export SUPABASE_S3_ENDPOINT="https://aqbtiobrpwstjbbwtqap.storage.supabase.co/storage/v1/s3"; \
	export SUPABASE_S3_BUCKET="zworkforce"; \
	export SUPABASE_EXPECTED_PROJECT_REF="aqbtiobrpwstjbbwtqap"; \
	$(PYTHON_VENV) scripts/supabase_stagef_vault_setup.py

# ------------------------------------------------------------------------------
# Cloudflare / Terraform
# ------------------------------------------------------------------------------

CLOUDFLARE_STACK := infrastructure/terraform/cloudflare

cloudflare-plan:
	@test -n "$${TF_VAR_cloudflare_api_token:-}" || (echo "set TF_VAR_cloudflare_api_token" >&2; exit 2)
	@test -n "$${TF_VAR_cloudflare_account_id:-}" || (echo "set TF_VAR_cloudflare_account_id" >&2; exit 2)
	@test -n "$${TF_VAR_cloudflare_zone_id:-}" || (echo "set TF_VAR_cloudflare_zone_id" >&2; exit 2)
	@test -n "$${TF_VAR_cloudflare_tunnel_id:-}" || (echo "set TF_VAR_cloudflare_tunnel_id" >&2; exit 2)
	cd $(CLOUDFLARE_STACK) && terraform init && terraform validate && terraform plan -out=tfplan
	@echo "Terraform plan created. Review before applying."

cloudflare-apply:
	@test -n "$${approved_plan_sha256:-}" || (echo "set approved_plan_sha256 (from plan mode output)" >&2; exit 2)
	cd $(CLOUDFLARE_STACK) && terraform apply -auto-approve tfplan

cloudflare-status:
	@echo "=== Cloudflare stack files ==="
	@ls -la $(CLOUDFLARE_STACK)/*.tf $(CLOUDFLARE_STACK)/*.tfvars.example 2>/dev/null || true
	@echo ""
	@echo "=== Terraform validate ==="
	@cd $(CLOUDFLARE_STACK) && terraform validate 2>&1 || true

# ------------------------------------------------------------------------------
# Runtime
# ------------------------------------------------------------------------------

PID_FILE ?= /tmp/zworkforce.pid
LOG_FILE ?= /tmp/zworkserve.log
ZWF_PORT ?= 9569

run:
	$(PYTHON) -m zworkforce serve

start:
	@if curl -s --connect-timeout 2 http://127.0.0.1:$(ZWF_PORT)/health >/dev/null 2>&1; then \
		echo "zWorkforce already online on port $(ZWF_PORT)"; \
	else \
		nohup $(PYTHON) -m zworkforce serve > $(LOG_FILE) 2>&1 & \
		echo $$! > $(PID_FILE); \
		sleep 2; \
		if curl -s --connect-timeout 5 http://127.0.0.1:$(ZWF_PORT)/health >/dev/null 2>&1; then \
			echo "zWorkforce started on port $(ZWF_PORT) (PID $$(cat $(PID_FILE)))"; \
		else \
			echo "zWorkforce failed to start. See $(LOG_FILE)"; \
			exit 1; \
		fi; \
	fi

stop:
	-@if [ -f "$(PID_FILE)" ]; then \
		PID=$$(cat "$(PID_FILE)" 2>/dev/null || true); \
		if [ -n "$$PID" ] && kill -0 "$$PID" 2>/dev/null; then \
			kill -TERM "$$PID" 2>/dev/null || true; \
			sleep 2; \
			if kill -0 "$$PID" 2>/dev/null; then \
				kill -KILL "$$PID" 2>/dev/null || true; \
			fi; \
			rm -f "$(PID_FILE)" 2>/dev/null || true; \
			echo "zWorkforce stopped (PID $$PID)"; \
		else \
			rm -f "$(PID_FILE)" 2>/dev/null || true; \
			echo "zWorkforce PID $$PID not running"; \
		fi; \
	else \
		echo "No PID file found at $(PID_FILE)"; \
	fi
	-@pkill -f "python -m zworkforce serve" 2>/dev/null || true

restart: stop start

status:
	@if curl -s --connect-timeout 2 http://127.0.0.1:$(ZWF_PORT)/health >/dev/null 2>&1; then \
		STATUS=$$(curl -s --connect-timeout 2 http://127.0.0.1:$(ZWF_PORT)/health 2>/dev/null); \
		echo "zWorkforce: ONLINE (port $(ZWF_PORT))"; \
		echo "$$STATUS"; \
	else \
		echo "zWorkforce: OFFLINE (port $(ZWF_PORT))"; \
		if [ -f "$(PID_FILE)" ]; then \
			PID=$$(cat "$(PID_FILE)"); \
			if kill -0 "$$PID" 2>/dev/null; then \
				echo "PID $$PID exists but port $(ZWF_PORT) not responding"; \
			else \
				echo "PID $$PID is not running"; \
			fi; \
		fi; \
	fi

worker:
	$(PYTHON) -m zworkforce worker

scheduler:
	$(PYTHON) -m zworkforce scheduler --once

docker-build:
	docker build --build-arg VERSION=$(VERSION) -t zworkforce:$(VERSION) .

# ------------------------------------------------------------------------------
# Full validation
# ------------------------------------------------------------------------------

full-validation: compile test doctor sec-scan env-check
	@if [ -n "$${ZWORKFORCE_TEST_POSTGRES_URL:-}" ]; then \
		$(MAKE) postgres-test; \
	else \
		echo "Skipping postgres-test: ZWORKFORCE_TEST_POSTGRES_URL not set"; \
	fi
	@echo "Full validation complete."

ci-validation: compile test doctor sec-scan
	@echo "CI validation complete."
