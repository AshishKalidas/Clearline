-include .docker-context.local
COMPOSE := $(shell command -v docker-compose >/dev/null 2>&1 && echo docker-compose || echo docker compose)
RUN := $(COMPOSE) exec -T api

.PHONY: up down migrate seed test lint typecheck eval eval-claude eval-mimo results evidence evidence-check demo purge mcp-check
up:
	$(COMPOSE) up -d --build --wait
down:
	$(COMPOSE) down
migrate:
	$(RUN) alembic upgrade head
test:
	$(RUN) python -m pytest --cov=backend/app --cov-report=term-missing --cov-fail-under=85
lint:
	$(RUN) ruff check .
	$(RUN) ruff format --check .
typecheck:
	$(RUN) mypy --strict backend/app mcp_server evals
seed:
	$(RUN) python -m evals.generate_dataset --pdfs
	$(RUN) sh -c 'DATABASE_URL="$$MIGRATION_DATABASE_URL" python -m backend.app.ingest.seed'
purge:
	$(RUN) python -m backend.app.privacy.retention
eval:
	$(RUN) python -m evals.run_eval --llm stub --retrieval on
	$(RUN) python -m evals.run_eval --llm stub --retrieval off
	$(COMPOSE) cp api:/app/evals/reports/. evals/reports/
eval-claude:
	$(RUN) python -m evals.run_eval --llm claude --retrieval on
	$(RUN) python -m evals.run_eval --llm claude --retrieval off
	$(COMPOSE) cp api:/app/evals/reports/. evals/reports/
eval-mimo:
	$(RUN) python -m evals.run_eval --llm mimo --retrieval on
	$(RUN) python -m evals.run_eval --llm mimo --retrieval off
	$(COMPOSE) cp api:/app/evals/reports/. evals/reports/
results:
	cat EVALUATION_RESULTS.md | $(RUN) python -m evals.update_results --stdin > EVALUATION_RESULTS.generated.md
	mv EVALUATION_RESULTS.generated.md EVALUATION_RESULTS.md
evidence:
	$(RUN) python -m evals.export_evidence --stdout > web/src/generated/evidence.json.tmp
	mv web/src/generated/evidence.json.tmp web/src/generated/evidence.json
evidence-check:
	$(RUN) python -m evals.export_evidence --check
demo: up seed
	$(RUN) python -m backend.app.demo
	@demo_url="http://$$($(COMPOSE) port web 80)"; echo "Clearline: $$demo_url"; \
	if [ "$${CLEARLINE_NO_BROWSER:-0}" != 1 ]; then \
		if command -v open >/dev/null 2>&1; then open "$$demo_url" || true; \
		elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$$demo_url" || true; fi; \
	fi
mcp-check:
	$(RUN) python -m mcp_server.smoke
