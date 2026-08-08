SHELL := /bin/bash
PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff
API_URL ?= http://127.0.0.1:18000/api/v1
POSTGRES_HOST_PORT ?= 55432
HOST_DATABASE_URL ?= postgresql+psycopg://lore:lore@127.0.0.1:$(POSTGRES_HOST_PORT)/lore_studio

.PHONY: bootstrap dev up down logs test test-models migrate seed reindex backup restore lint build e2e validate

bootstrap:
	test -f .env || cp .env.example .env
	test -x $(PYTHON) || python3 -m venv .venv
	$(PYTHON) -m pip install -e './backend[dev]'
	npm --prefix frontend ci

dev up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f backend frontend db

test:
	APP_CONFIG_ROOT=$(CURDIR)/config $(PYTEST) -q

test-models:
	RUN_LOCAL_MODEL_TESTS=true RUN_EMBEDDING_TESTS=true RUN_VISION_TESTS=true \
	WRITER_MODEL_BASE_URL=$${WRITER_MODEL_BASE_URL:-http://127.0.0.1:8080/v1} \
	UTILITY_MODEL_BASE_URL=$${UTILITY_MODEL_BASE_URL:-http://127.0.0.1:8080/v1} \
	VISION_MODEL_BASE_URL=$${VISION_MODEL_BASE_URL:-http://127.0.0.1:8080/v1} \
	EMBEDDING_BASE_URL=$${EMBEDDING_BASE_URL:-http://127.0.0.1:8081/v1} \
	$(PYTEST) -q backend/tests/test_local_models.py

migrate:
	docker compose up -d db
	docker compose run --rm backend alembic upgrade head

seed:
	LORE_STUDIO_API=$(API_URL) $(PYTHON) scripts/seed_world.py

reindex:
	LORE_STUDIO_API=$(API_URL) $(PYTHON) scripts/reindex_all.py

backup:
	mkdir -p backups
	docker compose exec -T db pg_dump -U $${POSTGRES_USER:-lore} -d $${POSTGRES_DB:-lore_studio} -Fc > "backups/lore-studio-$$(date +%Y%m%d-%H%M%S).dump"

restore:
	test "$(RESTORE_CONFIRM)" = "restore-lore-studio"
	test -f "$(RESTORE_FILE)"
	docker compose exec -T db pg_restore --clean --if-exists --no-owner -U $${POSTGRES_USER:-lore} -d $${POSTGRES_DB:-lore_studio} < "$(RESTORE_FILE)"

lint:
	$(RUFF) check backend scripts

build:
	npm --prefix frontend run build
	docker compose build backend frontend

e2e:
	E2E_EXPECT_DATA=true PLAYWRIGHT_CHROMIUM_PATH=$${PLAYWRIGHT_CHROMIUM_PATH:-/snap/bin/chromium} npm --prefix frontend run test:e2e

validate:
	$(PYTHON) scripts/validate_bundle.py
	docker compose config --quiet
