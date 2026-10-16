.DEFAULT_GOAL := help

UV ?= uv

.PHONY: help sync venv collections install lint lock

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

sync: ## Sync the Python environment from uv.lock (including lint tools)
	$(UV) sync --locked

venv: sync ## Compatibility alias for sync

collections: sync ## Install Galaxy collections (separate from uv dependencies)
	$(UV) run --locked ansible-galaxy collection install -r requirements.yml

install: collections ## Install the complete controller environment

# Use real vault credentials when available; otherwise allow offline syntax checks.
lint: install ## Run ansible-lint
	ANSIBLE_VAULT_PASSWORD=$${ANSIBLE_VAULT_PASSWORD:-lint} $(UV) run --locked ansible-lint

lock: ## Refresh uv.lock after editing pyproject.toml
	$(UV) lock
