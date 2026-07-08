PYTHON ?= python3

.PHONY: help validate

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

validate: ## Validate org manifests and bindings against the spec
	@$(PYTHON) tools/validate.py

clean:
	find . -name '.fuse_hidden*' -delete