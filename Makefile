.PHONY: test deploy docker-build docker-up docker-down smoke-test lint format

test:
	python -m pytest --tb=short -q
	ruff check .

lint:
	ruff check .
	ruff format --check

format:
	ruff format .

deploy:
	python scripts/deploy_unified.py

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

smoke-test:
	curl -sf http://127.0.0.1:8081/dlc/tasks/validate && echo " dlc/validate OK" || (echo " dlc/validate FAILED" && exit 1)
	curl -sf http://127.0.0.1:8081/health && echo " health OK" || (echo " health FAILED" && exit 1)
