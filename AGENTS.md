# english — Agent Guide

> Cross-tool fallback (Cursor, Aider, Codex, Jules, Claude Code). Mirrors `.claude/memory-bank/`.

## Overview
**Executive English** — персональный mobile-first PWA-аудиотренажёр бизнес-английского *говорения*
(один пользователь — Алексей). Кураторские батчи executive-фраз учатся через 3-урочный flow
(мнемо-основа → фразы → тесты) с устным recall и оценкой. Прод: `https://executive-english.net`
за cookie-гейтом. Полный паспорт: `.claude/memory-bank/projectbrief.md`.

## Stack
- **Backend:** Python 3.12, FastAPI + SQLModel + Pydantic v2, SQLite (WAL). Роутеры в
  `backend/app/routers/{batches,imports,sessions,settings,training}.py`; модули
  `app/{config,db,models,schemas,importer,llm,tts,stt,scoring,audio,mnemo,content,cover}.py`.
- **Frontend:** React 18 + Vite + TypeScript, PWA (vanilla service worker). `createHashRouter`.
  Страницы в `frontend/src/pages/`, токены/стили в `frontend/src/index.css`.
- **Audio:** OpenAI TTS (`tts-1` / `gpt-4o-mini-tts`), gapless WAV-конкат на чистом Python (`wave`).
- **STT/scoring:** `gpt-4o-mini-transcribe` + LLM-скоринг (локальный gate → `gpt-4.1-nano`/`-mini`).
- **LLM:** провайдер-абстракция — Meridian (Hetzner `172.17.0.1:3456`) → Anthropic-direct → OpenAI.

## Setup (local dev)
```bash
# backend
cd backend && python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
set -a; . ~/Documents/AI/Claude/.env; set +a      # OPENAI/ANTHROPIC ключи
uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm install && npm run dev          # :5173, проксирует /api → :8000
```

## Build & deploy
```bash
# 1) собрать фронт ЛОКАЛЬНО (на хост едет готовый dist)
cd frontend && npm run build                       # tsc -b && vite build
# 2) rsync на Hetzner (ИСКЛЮЧАЕТ .env, data, node_modules)
rsync -az --exclude='.git' --exclude='.claude' --exclude='backend/.venv' \
  --exclude='backend/data' --exclude='frontend/node_modules' --exclude='__pycache__' \
  --exclude='.env' --exclude='.dockerignore' -e 'ssh -i ~/.ssh/antigravity_key' \
  ~/Documents/AI/Claude/english/ root@89.167.122.76:/root/english/
# 3) пересобрать ТОЛЬКО english_app (чужие контейнеры не трогать!)
ssh -i ~/.ssh/antigravity_key root@89.167.122.76 \
  'cd /root/english && docker compose -p english -f docker-compose.deploy.yml up -d --build english_app'
```
Проверка после деплоя: `/api/batches`→401, `/login`→200, `index.html`→ новый бандл, контейнер Up.

## Code style
- **Дизайн — строго по `DESIGN.md`** (фирменный зелёный `--map-green` #1C8C63, без синего/фиолетового/красного,
  glass только в навигации, без геймификации). Не хардкодить цвета — использовать CSS-vars из `index.css`.
- Page-scoped CSS-префиксы: `.l3-*` (Урок 3), `.bh-*` (обзор батча), `.nav-*` (floating dock).
- Визуальный гид (рендер): `frontend/public/design-system.html` → `executive-english.net/design-system.html`.
- iOS-нюансы: запись только по жесту (pointer events надёжнее `:active`); `font-size:16px` в инпутах (нет зума).

## Testing
Формальных тестов нет. Верификация: `npm run build` (typecheck) + локальный `vite preview` со
скриншотами/DOM-проверкой через Playwright (stub `window.fetch` для данных). Бэкенд — `python3 -c "import ast"`
синтакс-чек + smoke через uvicorn. Финальная проверка iOS-аудио — только на устройстве Алексея.

## Safety considerations
- **Hetzner `89.167.122.76` — SHARED PROD host.** Деплой/рестарт/билд — **только с явного approval**.
  Трогать ТОЛЬКО контейнеры `english_*`; никаких stop/rm/prune/restart чужих.
- **Cookie-гейт не снимать:** `ENGLISH_APP_PASSWORD` не пустой, `:8000` наружу не публиковать;
  `/api/*` и `/audio/*` без cookie → 401, страницы → `/login`.
- **Секреты не печатать/не коммитить** (`OPENAI_API_KEY`, `ENGLISH_APP_PASSWORD`, `ENGLISH_COOKIE_SECRET`);
  `.env` живёт на хосте (`/root/english/.env`, perms 600), исключён из rsync.
- **TLS — в чужом `go_caddy`**: править только аддитивно свой site-блок + `caddy reload`.
- **Платный gpt-image-1 / TTS — только с явным approval.** Деплой только когда Лёша скажет.

## For more context
`.claude/CLAUDE.md` (Claude Code entrypoint) и `.claude/memory-bank/` (6 файлов: projectbrief, architecture,
techContext, accessAndSafety, activeContext, progress) + `DESIGN.md` (дизайн-язык).
