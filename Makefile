-include .docker-context.local
COMPOSE := $(shell command -v docker-compose >/dev/null 2>&1 && echo docker-compose || echo docker compose)
RUN := $(COMPOSE) exec -T api

.PHONY: up down migrate seed test lint typecheck eval eval-claude eval-mimo results demo purge
up:
	$(COMPOSE) up -d --build
down:
	$(COMPOSE) down
migrate:
	$(RUN) alembic upgrade head
test:
	$(RUN) python -m pytest --cov=backend/app --cov-report=term-missing
lint:
	$(RUN) ruff check .
	$(RUN) ruff format --check .
typecheck:
	$(RUN) mypy --strict backend/app
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
	cat README.md | $(RUN) python -m evals.update_results --stdin > README.generated.md
	mv README.generated.md README.md
