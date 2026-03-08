.PHONY: install dev test test-unit test-integration docker-build docker-run deploy load-demo lint clean

# ── Install ──────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# ── Development ──────────────────────────────────────────────────
dev:
	cd app && uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# ── Testing ──────────────────────────────────────────────────────
test:
	cd app && python -m pytest ../tests/ -v --tb=short

test-unit:
	cd app && python -m pytest ../tests/test_ontology.py ../tests/test_tools.py -v --tb=short

test-integration:
	cd app && python -m pytest ../tests/test_api.py ../tests/test_mediation.py -v --tb=short

test-cov:
	cd app && python -m pytest ../tests/ -v --cov=. --cov-report=term-missing --tb=short

# ── Docker ───────────────────────────────────────────────────────
docker-build:
	docker build -t concordia .

docker-run:
	docker run -p 8080:8080 -e GOOGLE_API_KEY=$${GOOGLE_API_KEY} concordia

# ── Cloud Run ────────────────────────────────────────────────────
deploy:
	bash deploy.sh

# ── Demo ─────────────────────────────────────────────────────────
load-demo:
	python demo/load_scenario.py demo/scenarios/hr_dispute.json

load-all-demos:
	python demo/load_scenario.py demo/scenarios/hr_dispute.json
	python demo/load_scenario.py demo/scenarios/lease_dispute.json
	python demo/load_scenario.py demo/scenarios/family_estate.json

# ── Lint ─────────────────────────────────────────────────────────
lint:
	ruff check app/ tests/

# ── Clean ────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
