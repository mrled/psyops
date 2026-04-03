help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install Ansible collections from requirements.yml
	.venv/bin/ansible-galaxy collection install -r requirements.yml

# Run ansible-lint with a dummy vault password.
# Vault-encrypted files are excluded from linting already;
# the dummy password just allows ansible-playbook --syntax-check to run.
# In environments with real credentials (1Password, GPG, or ANSIBLE_VAULT_PASSWORD set),
# the vault-pass-script uses those instead.
lint: install ## Run ansible-lint
	ANSIBLE_VAULT_PASSWORD=$${ANSIBLE_VAULT_PASSWORD:-lint} .venv/bin/ansible-lint

.PHONY: help install lint
