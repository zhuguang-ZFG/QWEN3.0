.PHONY: test deploy docker-build docker-up docker-down smoke-test lint format

test:
	pytest --tb=short -q
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
	curl -sf http://127.0.0.1:8080/health && echo " OK" || (echo " FAILED" && exit 1)
	curl -sf http://127.0.0.1:8080/v1/models | python -m json.tool > /dev/null && echo "models endpoint OK"
