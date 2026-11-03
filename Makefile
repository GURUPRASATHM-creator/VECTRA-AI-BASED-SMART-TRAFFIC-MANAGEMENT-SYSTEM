.PHONY: up down build logs ps restart clean

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

ps:
	docker compose ps

restart:
	docker compose restart

# removes containers AND volumes (Postgres/MinIO data) — full reset
clean:
	docker compose down -v
