.PHONY: up down logs ps demo demo-agent evidence reset lint test

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

demo:
	docker compose exec tools python scripts/demo_seed_and_publish.py
	docker compose exec tools python scripts/demo_request_trade.py
	docker compose exec tools python scripts/demo_approve_trade.py
	docker compose exec tools python scripts/demo_show_audit.py

demo-agent:
	docker compose exec tools python scripts/demo_agentic_trade.py

evidence:
	bash scripts/export_evidence.sh

reset:
	docker compose down -v
	docker compose up -d --build

lint:
	docker compose exec tools ruff check .

test:
	docker compose exec tools pytest -q
