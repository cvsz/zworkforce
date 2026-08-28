SHELL := /usr/bin/env bash
.SHELLFLAGS := -Eeuo pipefail -c
.DEFAULT_GOAL := help
.DELETE_ON_ERROR:

PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

.PHONY: help env-init install install-dry-run install-systemd host-bootstrap-dry-run vm-snapshot-dry-run update-check update \
	sign-update-manifest auto-update-dry-run auto-update test lint validate validate-shell sbom run build up down logs health \
	client-key-hash lock validate-locks validate-container clean

help: ## Show commands
	@awk 'BEGIN {FS = ":.*## "; print "ZeaZ Provider"} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

env-init: ## Create local config and secrets without overwriting files
	@test ! -e .env || { echo ".env already exists"; exit 2; }
	@test ! -e config/providers.yaml || { echo "config/providers.yaml already exists"; exit 2; }
	@cp .env.example .env
	@sed -i "s/replace-with-generated-client-key/$$(openssl rand -hex 32)/" .env
	@cp config/providers.example.yaml config/providers.yaml
	@chmod 600 .env

install: ## Install development environment
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(PIP) install --require-hashes -r requirements-build.lock
	@$(PIP) install --require-hashes -r requirements-dev.lock
	@$(PIP) install --no-build-isolation --no-deps -e .

lock: ## Regenerate reviewed, hashed dependency locks
	@$(VENV)/bin/pip-compile --generate-hashes --resolver=backtracking --strip-extras \
		--output-file=requirements.lock pyproject.toml
	@$(VENV)/bin/pip-compile --generate-hashes --resolver=backtracking --strip-extras \
		--extra=dev --output-file=requirements-dev.lock pyproject.toml
	@$(VENV)/bin/pip-compile --generate-hashes --resolver=backtracking --strip-extras \
		--output-file=requirements-build.lock requirements-build.in

install-dry-run: ## Preview standalone versioned installation
	@bash scripts/install.sh --dry-run

install-systemd: ## Install and enable user service with CONFIRM_INSTALL=yes
	@test "$(CONFIRM_INSTALL)" = "yes" || { echo "Set CONFIRM_INSTALL=yes"; exit 2; }
	@bash scripts/install.sh --apply --systemd-user

host-bootstrap-dry-run: ## Preview Ubuntu 26.04 host setup without changing it
	@bash scripts/bootstrap-host.sh --dry-run

vm-snapshot-dry-run: ## Preview the fresh Ubuntu 26.04 VMware acceptance test
	@test -n "$(VM_HOST)" -a -n "$(VM_INSTALL_USER)" || \
		{ echo "Set VM_HOST and VM_INSTALL_USER"; exit 2; }
	@bash scripts/test-vm-snapshot.sh --dry-run --host "$(VM_HOST)" --install-user "$(VM_INSTALL_USER)" \
		$(if $(VM_IDENTITY_FILE),--identity-file "$(VM_IDENTITY_FILE)") \
		$(if $(VM_SUDO_MODE),--sudo-mode "$(VM_SUDO_MODE)")

update-check: ## Check the configured HTTPS release manifest
	@bash scripts/update.sh --check

update: ## Apply checksum-verified update with CONFIRM_UPDATE=yes
	@CONFIRM_UPDATE="$(CONFIRM_UPDATE)" bash scripts/update.sh --apply

sign-update-manifest: ## Sign MANIFEST with an Ed25519 PRIVATE_KEY
	@test -n "$(MANIFEST)" -a -n "$(PRIVATE_KEY)" || \
		{ echo "Set MANIFEST and PRIVATE_KEY"; exit 2; }
	@bash scripts/sign-update-manifest.sh "$(MANIFEST)" "$(PRIVATE_KEY)" $(if $(SIGNATURE),"$(SIGNATURE)")

auto-update-dry-run: ## Preview daily verified auto-update timer
	@bash scripts/install-auto-update.sh --dry-run

auto-update: ## Enable daily verified updates with CONFIRM_AUTO_UPDATE=yes
	@CONFIRM_AUTO_UPDATE="$(CONFIRM_AUTO_UPDATE)" bash scripts/install-auto-update.sh --apply

test: ## Run tests
	@$(PY) -m pytest -q

lint: ## Run Ruff
	@$(PY) -m ruff check .

validate-shell: ## Parse-check installer and maintenance scripts
	@find scripts -type f -name '*.sh' -exec bash -n {} +

validate-locks: ## Check dependency locks and their enforced install paths
	@$(PY) scripts/validate-locks.py

validate: ## Compile, lint, and test
	@$(MAKE) --no-print-directory validate-shell
	@$(MAKE) --no-print-directory validate-locks
	@$(PY) -m compileall -q src
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory test

sbom: ## Generate CycloneDX JSON SBOM
	@$(PY) scripts/generate-sbom.py dist/sbom.cdx.json

run: ## Start local gateway
	@ZEAZ_CONFIG=config/providers.yaml $(VENV)/bin/zeaz-provider

build: ## Build hardened container
	@docker compose build

validate-container: ## Prove runtime user, filesystem, capability, and privilege boundaries
	@bash scripts/validate-container.sh

up: ## Start standalone gateway
	@docker compose up -d

down: ## Stop gateway and retain config
	@docker compose down

logs: ## Show recent logs
	@docker compose logs --tail 200 provider

health: ## Check readiness
	@curl -fsS http://127.0.0.1:$${ZEAZ_PORT:-8080}/health/ready

client-key-hash: ## Prompt securely and print a SHA-256 client-key digest
	@$(PY) scripts/hash-client-key.py

clean: ## Preview generated local files only
	@find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -print
