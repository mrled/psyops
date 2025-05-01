.SUFFIXES:

# KNTY on a phone keypad
DEVPORT := 5689

.PHONY: help
help: ## Show this help
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: clean
clean: ## Remove venv, builds, etc
	rm -rf public resources

.PHONY: modget
modget:
	hugo mod get -u ./...

.PHONY: dev
dev: modget ## Run a dev server for the labnotes
	hugo serve --port $(DEVPORT)

.PHONY: production
production: modget ## Build the labnotes site for production
	hugo
