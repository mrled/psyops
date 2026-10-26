.DEFAULT_GOAL := help

UV ?= uv
# Keep activated environments and uv overrides from redirecting project installs.
UV_RUN = env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT UV_PYTHON_DOWNLOADS=automatic $(UV)

.PHONY: help venvs venv-ansible venv-macrofactor venv-telekinesis \
	venv-progfiguration-blacksite venv-neuralupgrade \
	venv-chineseroom-webhook-receiver venv-kvrb

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

venvs: ## Set up all project environments (preview with make -n venvs)
venvs: venv-ansible venv-macrofactor venv-telekinesis \
	venv-progfiguration-blacksite venv-neuralupgrade \
	venv-chineseroom-webhook-receiver venv-kvrb

# Locked projects: reuse their declared Python versions and dependency groups.
venv-ansible: ## Set up Ansible
	$(UV_RUN) sync --locked --project ansible

venv-macrofactor: ## Set up MacroFactor
	$(UV_RUN) sync --locked --project pipelines/macrofactor

# Unlocked packages: preserve existing environments and install editable packages
# with their development extras, without generating new lockfiles.
venv-telekinesis: ## Set up Telekinesis
	test -x telekinesis/.venv/bin/python || $(UV_RUN) venv --python '>=3.10' telekinesis/.venv
	$(UV_RUN) pip install --python telekinesis/.venv/bin/python -e './telekinesis[development]'

venv-progfiguration-blacksite: ## Set up Blacksite
	test -x progfiguration_blacksite/.venv/bin/python || $(UV_RUN) venv --python '>=3.10' progfiguration_blacksite/.venv
	$(UV_RUN) pip install --python progfiguration_blacksite/.venv/bin/python -e './progfiguration_blacksite[development]'

venv-neuralupgrade: ## Set up neuralupgrade
	test -x psyopsOS/neuralupgrade/.venv/bin/python || $(UV_RUN) venv --python '>=3.10' psyopsOS/neuralupgrade/.venv
	$(UV_RUN) pip install --python psyopsOS/neuralupgrade/.venv/bin/python -e './psyopsOS/neuralupgrade[development]'

WEBHOOK_RECEIVER := ansible/roles/chineseroom_gitea/files/chineseroom_webhook_receiver
venv-chineseroom-webhook-receiver: ## Set up the webhook receiver
	test -x $(WEBHOOK_RECEIVER)/.venv/bin/python || $(UV_RUN) venv --python '>=3.9' $(WEBHOOK_RECEIVER)/.venv
	$(UV_RUN) pip install --python $(WEBHOOK_RECEIVER)/.venv/bin/python -e ./$(WEBHOOK_RECEIVER)

# kvrb has no third-party Python dependencies and no installable build backend.
KVRB := seedboxk8s/applications/restic-backup/kvrb
venv-kvrb: ## Set up kvrb
	test -x $(KVRB)/.venv/bin/python || $(UV_RUN) venv --python '>=3.11' $(KVRB)/.venv
