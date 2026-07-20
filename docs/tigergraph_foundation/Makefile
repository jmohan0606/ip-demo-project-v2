.PHONY: validate static-test mock-test release-audit backend frontend reset live-install live-validate clean

validate: static-test mock-test

static-test:
	python scripts/validate_package.py
	python scripts/validate_query_semantics.py
	python scripts/audit_gsql_queries.py
	python scripts/validate_query_cases_data.py
	python scripts/validate_loading_jobs.py
	python scripts/validate_business_scenarios.py
	python scripts/check_no_placeholders.py
	cd backend && PYTHONPATH=. pytest -q
	cd backend && python -m compileall -q app tests
	cd frontend && npm run build

mock-test:
	python scripts/run_full_mock_ingestion.py

release-audit:
	PYTHONDONTWRITEBYTECODE=1 python scripts/release_audit.py

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

reset:
	python scripts/reset_tracker.py

live-install:
	bash scripts/install_tigergraph.sh

live-validate:
	python scripts/live_tigergraph_validation.py

clean:
	rm -rf backend/app/__pycache__ backend/app/routers/__pycache__ backend/app/services/__pycache__ backend/tests/__pycache__ frontend/dist frontend/node_modules runtime/*.db runtime/*.db-wal runtime/*.db-shm
