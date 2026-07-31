SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help bootstrap bootstrap-core doctor run run-lowvram run-wan \
        models model-status repo-check snapshot update nodes serve serve-ui forget forget-all audit

help: ## Show this help
	@echo "ai-video-gen — available targets"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Model weights are never downloaded by these targets except 'models'."

bootstrap: ## Full idempotent setup (no model downloads)
	./bootstrap.sh

bootstrap-core: ## Setup without model manifest summary
	./bootstrap.sh --core-only

doctor: ## Health check (PASS/WARN/FAIL)
	./scripts/doctor.sh

run: ## Start ComfyUI, normal VRAM mode
	./scripts/comfy.sh image

run-lowvram: ## Start ComfyUI, low-VRAM mode
	./scripts/comfy.sh lowvram

run-wan: ## Start ComfyUI with the most conservative settings (Wan 2.2)
	./scripts/comfy.sh wan

models: ## List model profiles
	./scripts/modelctl list

model-status: ## Show active profile, installed artifacts and disk usage
	./scripts/modelctl status

nodes: ## List declared custom nodes
	./scripts/custom-nodectl list

repo-check: ## Repository safety scan (staged + tracked)
	./scripts/repository-check.sh --all

snapshot: ## Write an environment snapshot report
	./scripts/snapshot.sh

update: ## Deliberate ComfyUI submodule + environment update
	./scripts/update.sh

serve: ## Start the local web UI (and ComfyUI behind it)
	./scripts/serve.sh

serve-ui: ## Start only the web UI (ComfyUI must already be running)
	./scripts/serve.sh --no-engine

forget: ## Erase a generation completely: make forget JOB=<id>
	./scripts/forget-generation $(JOB)

forget-all: ## Erase EVERY generation and its files
	./scripts/forget-generation --all

audit: ## Report any generation residue left on disk
	./scripts/forget-generation --audit
