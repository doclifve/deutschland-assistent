.PHONY: test test-backend build-web up

test: test-backend

test-backend:
	cd services/civic-core && python -m pytest -q

build-web:
	cd apps/web && npm install && npm run build

up:
	docker compose up --build
