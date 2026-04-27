# Slackbot — multi-tenant FastAPI

## Local setup

1. Install Postgres 14+ and Redis 6+ natively (see below).
2. Create venv, install deps:
```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
```
3. Copy env: `cp .env.example .env` and edit values.
4. Create DB + run migrations:
```bash
   alembic upgrade head
   python -m scripts.seed
```
5. Run the app:
```bash
   uvicorn app.main:app --reload --port 8000
```
6. Expose to Slack:
```bash
   ngrok http 8000
```

## Postgres native install

- **macOS:** `brew install postgresql@16 && brew services start postgresql@16`
- **Windows:** download installer from postgresql.org
- **Linux:** `sudo apt install postgresql && sudo systemctl start postgresql`

Then create the DB and user:
```sql
CREATE USER slackbot WITH PASSWORD 'slackbot';
CREATE DATABASE slackbot OWNER slackbot;
```

## Redis native install

- **macOS:** `brew install redis && brew services start redis`
- **Windows:** use Memurai or WSL2 (Redis isn't natively supported on Windows)
- **Linux:** `sudo apt install redis-server && sudo systemctl start redis`

## Project layout

- `app/core/` — db, redis, logging, contextvars
- `app/middleware/` — tenant resolver
- `app/models/` — SQLAlchemy models
- `app/services/` — business logic (bot routing, command handling, sending)
- `app/api/` — HTTP routes (Slack + admin JSON)
- `app/ui/` — Jinja2 admin UI
- `alembic/` — migrations
- `scripts/` — one-off scripts (seed)