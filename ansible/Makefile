.DEFAULT_GOAL := help

UV ?= uv

URESTIC_ROLE := roles/urestic
URESTIC_PYTHON := $(URESTIC_ROLE)/files $(URESTIC_ROLE)/tests

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

.PHONY: sync
sync: ## Sync the Python environment from uv.lock (including lint tools)
	$(UV) sync --locked

.PHONY: venv
venv: sync ## Compatibility alias for sync

.PHONY: collections
collections: sync ## Install Galaxy collections (separate from uv dependencies)
	$(UV) run --locked ansible-galaxy collection install -r requirements.yml

.PHONY: install
install: collections ## Install the complete controller environment

# Use real vault credentials when available; otherwise allow offline syntax checks.
.PHONY: lint
lint: install ## Run ansible-lint
	ANSIBLE_VAULT_PASSWORD=$${ANSIBLE_VAULT_PASSWORD:-lint} $(UV) run --locked ansible-lint

.PHONY: lint-urestic
lint-urestic: ## Check urestic role Python lint, formatting, types, and Ansible lint
	$(UV) run --locked ruff check $(URESTIC_PYTHON)
	$(UV) run --locked ruff format --check $(URESTIC_PYTHON)
	$(UV) run --locked ty check --error-on-warning $(URESTIC_PYTHON)
	ANSIBLE_VAULT_PASSWORD=$${ANSIBLE_VAULT_PASSWORD:-lint} $(UV) run --locked ansible-lint $(URESTIC_ROLE)

.PHONY: format-urestic
format-urestic: ## Format the urestic role Python sources
	$(UV) run --locked ruff format $(URESTIC_PYTHON)

.PHONY: test-urestic
test-urestic: ## Run urestic cache and backup tests and controller-side smoke tests
	$(UV) run --locked python -m unittest discover -s $(URESTIC_ROLE)/tests -p 'test_*.py'
	ANSIBLE_VAULT_PASSWORD=$${ANSIBLE_VAULT_PASSWORD:-lint} $(UV) run --locked ansible-playbook -i localhost, $(URESTIC_ROLE)/tests/render.yml

.PHONY: check-urestic
check-urestic: lint-urestic test-urestic ## Run all urestic role checks

.PHONY: lock
lock: ## Refresh uv.lock after editing pyproject.toml
	$(UV) lock
