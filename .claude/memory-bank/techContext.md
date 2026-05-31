# Tech Context: english

> **Stack, infra, env vars. Updates when stack changes.**

## Stack
- Language: Python 3.12 (backend), TypeScript / Node 22 (frontend)
- Framework: FastAPI + SQLModel (backend), React 18 + Vite (frontend, PWA)
- DB: SQLite (WAL mode), файл `backend/data/app.db`
- Audio: OpenAI TTS (`tts-1`), gapless render на чистом Python (`wave`); ffmpeg опц.
- LLM: provider abstraction — Meridian (Hetzner) / Anthropic-direct / OpenAI

## Hosting / infra
- Where it runs: Hetzner `89.167.122.76`, Docker контейнер `english_*` (SHARED PROD — деплой только с approval)
- Deployment: Docker + Caddy reverse-proxy, поддомен `english.<domain>`, basic-auth
- Local dev: backend на `:8000` (uvicorn), frontend на `:5173` (vite), прокси `/api`→8000

## Environment variables (refs)
Все ключи — в master `.env` (`~/Documents/AI/Claude/.env`). Используются:
- `OPENAI_API_KEY` — OpenAI TTS (озвучка). Биллинг по входным символам.
- `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` — LLM-фолбэк локально (когда Meridian недоступен).
- Meridian: `http://172.17.0.1:3456` — только внутри Hetzner.
Backend читает их через `app/config.py` (pydantic-settings), плюс собственные: `ENGLISH_DATA_DIR`, `ENGLISH_LLM_PROVIDER`, `ENGLISH_TTS_MODEL`, `ENGLISH_TTS_VOICE`.

## Local dev
```bash
# backend
cd backend && ~/.local/bin/python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
set -a; . ~/Documents/AI/Claude/.env; set +a   # подтянуть OPENAI/ANTHROPIC ключи
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend && npm install && npm run dev   # :5173, проксирует /api на :8000
```

## Build / deploy
```bash
# Docker (локально собрать/прогнать)
docker compose up --build
# Hetzner: ТОЛЬКО с явного approval (shared prod host)
```

## Common operations
- Импорт демо-батча: `curl -X POST :8000/api/imports/parse -d @sample.json`
- Бэкап: copy `backend/data/app.db` (WAL-safe) + `backend/data/audio/` + `data/exports/`
- Сброс БД (dev): удалить `backend/data/app.db*`
