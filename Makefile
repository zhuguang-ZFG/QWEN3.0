.PHONY: test deploy docker-build docker-up docker-down smoke-test lint format clean install serve type-check

test:
	pytest --tb=short -q

lint:
	ruff check .
	ruff format --check

format:
	ruff format .

type-check:
	pyright

serve:
	python -m uvicorn server:app --host 0.0.0.0 --port 8080 --reload

install:
	pip install -r requirements_server.txt

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true

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
