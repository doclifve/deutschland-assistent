# Deutschland Assistent – Entwicklungsbefehle. `make help` zeigt alle Ziele.
PYTHON ?= python3
VENV   := services/civic-core/.venv
PY     := $(abspath $(VENV))/bin/python
API_PORT ?= 8000
WEB_PORT ?= 3000

.PHONY: help setup setup-backend setup-web env dev dev-backend dev-web dev-whatsapp \
        test test-backend test-whatsapp lint typecheck build-web check up clean

help: ## Diese Hilfe anzeigen
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n",$$1,$$2}'

env: ## .env aus .env.example anlegen (falls nicht vorhanden)
	@test -f .env || (cp .env.example .env && echo ".env angelegt")

setup: env setup-backend setup-web ## Alles installieren (Python-venv + npm)

setup-backend: ## Python-venv in services/civic-core/.venv anlegen und Abhängigkeiten installieren
	test -x $(PY) || $(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	cd services/civic-core && $(PY) -m pip install -q -e '.[dev]'
	$(PY) -m pip install -q -r channels/whatsapp-cloud/requirements.txt

setup-web: ## Web-Abhängigkeiten exakt nach package-lock.json installieren
	cd apps/web && npm ci

dev: ## Backend und Web parallel starten (Strg+C beendet beide)
	@$(MAKE) -j2 dev-backend dev-web

dev-backend: ## API mit Auto-Reload auf :8000
	cd services/civic-core && $(PY) -m uvicorn deutschland_assistent.main:app --reload --port $(API_PORT)

dev-web: ## Next.js-Dev-Server auf :3000
	cd apps/web && NEXT_PUBLIC_CIVIC_API_URL=$${NEXT_PUBLIC_CIVIC_API_URL:-http://localhost:$(API_PORT)} npx next dev -p $(WEB_PORT)

dev-whatsapp: ## WhatsApp-Adapter lokal auf :8010
	cd channels/whatsapp-cloud && CIVIC_CORE_URL=$${CIVIC_CORE_URL:-http://localhost:$(API_PORT)} $(PY) -m uvicorn app:app --reload --port 8010

test: test-backend test-whatsapp ## Alle Python-Tests

test-backend: ## Tests des Civic Core
	cd services/civic-core && $(PY) -m pytest -q

test-whatsapp: ## Tests des WhatsApp-Adapters
	cd channels/whatsapp-cloud && $(PY) -m pytest -q tests

lint: ## Ruff (Fehlerklassen F/E9) über Python-Code
	$(PY) -m ruff check --select F,E9 services/civic-core channels docs/media/rundgang

typecheck: ## TypeScript-Prüfung der Web-App
	cd apps/web && npx tsc --noEmit

build-web: ## Produktions-Build der Web-App
	cd apps/web && npm run build

check: lint test build-web ## Alles, was die CI prüft

up: env ## Gesamten Stack per Docker Compose starten
	docker compose up --build

clean: ## Build-Artefakte entfernen
	rm -rf apps/web/.next services/civic-core/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
