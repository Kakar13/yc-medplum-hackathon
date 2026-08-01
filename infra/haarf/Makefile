.PHONY: setup smoke run analyse clean test help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies
	pip install -r requirements.txt

test: ## Run unit tests
	python -m pytest tests/ -v

smoke: ## Smoke test: 1 trial, 1 scenario, baseline only
	python runner.py \
		--scenario scenarios/rt1_rbac_escalation.json \
		--condition baseline \
		--trials 1 \
		--seed 42 \
		--output results/

run: ## Full batch: all scenarios, both conditions, N=50
	python runner.py \
		--scenario all \
		--condition baseline haarf \
		--trials 50 \
		--seed 0 \
		--output results/

analyse: ## Compute metrics + 95% Wilson CIs
	python analyse.py \
		--results results/ \
		--output results/summary.csv

clean: ## Remove results
	rm -rf results/*.json results/summary.csv results/run_summary.json
