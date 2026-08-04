.PHONY: bootstrap up down logs test seed backend-shell

bootstrap:
	@test -f .env || cp .env.example .env
	@echo "Created .env if it did not exist."

up: bootstrap
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd backend && pytest -q

seed:
	python scripts/seed_demo.py

backend-shell:
	docker compose exec backend /bin/sh
