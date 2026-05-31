# Access & Safety: english

> **SSH/API endpoints + правила «не сломать».**

## Access points (HTTPS via shared go_caddy, 2026-05-31)
- **Live URL:** **https://executive-english.net** (зелёный замок, Let's Encrypt).
  Старый `http://89.167.122.76:8090` ещё работает (внутренний upstream), но КАНОНИЧЕСКИЙ —
  домен. ⚠️ Микрофон/запись голоса работают ТОЛЬКО по HTTPS (secure context) — по голому
  IP `navigator.mediaDevices === undefined`, поэтому весь тренировочный флоу был мёртв на телефоне
  до HTTPS. Теперь и PWA Service Worker регистрируется (install/offline).
- **HTTPS-цепочка:** `go_caddy` (TLS-терминация 443, общий фронт хоста) → `89.167.122.76:8090`
  (`english_caddy`, gzip) → `english_app:8000`. Тот же паттерн, что у atmos/kai.
- **TLS-конфиг живёт в ЧУЖОМ файле:** `/root/go_lesson_mvp/docker/Caddyfile` (контейнер
  `go_caddy` — это общий reverse-proxy всего сервера, держит 80/443; исторически из проекта
  kai-go, но обслуживает atmos+kai+english). Наш блок там:
  `executive-english.net { reverse_proxy 89.167.122.76:8090 }`. Бэкап перед правкой:
  `Caddyfile.bak-YYYYMMDD-HHMMSS` рядом. Применение: `docker exec go_caddy caddy validate ...`
  → `docker exec go_caddy caddy reload --config /etc/caddy/Caddyfile` (бесшовно, без даунтайма
  соседям). Сертификат авто-продлевает Caddy.
- **DNS:** `executive-english.net` — Squarespace-домен (NS = Google Domains), активен до 2027.
  A-запись `@ → 89.167.122.76`. Менять DNS — в Squarespace `DNS Settings` (нужен Лёша).
- **Auth: app-level cookie-гейт** (не basic-auth). Один раз вводишь пароль на странице
  `/login` → ставится подписанный HttpOnly-cookie `eng_auth` на 1 год (iOS Safari/PWA больше
  не переспрашивает). Пароль = `ENGLISH_APP_PASSWORD` в `/root/english/.env` (в репо не хранится).
  Логин/поле — кастомная HTML-форма, НЕ браузерный диалог basic-auth.
- **SSH host:** `ssh -i ~/.ssh/antigravity_key root@89.167.122.76` (shared prod host).
- **Containers:** `english_app` (uvicorn :8000, cookie-гейт в приложении, не публикуется наружу),
  `english_caddy` (публикует `8090:80`, чистый reverse_proxy). Compose project `-p english`.
- **Code on host:** `/root/english` (rsync с локального; деплой-файлы: `Dockerfile.deploy`,
  `docker-compose.deploy.yml`, `Caddyfile.ip`, `.env`).
- **Data volume:** `english_english_data` → `/srv/backend/data` (SQLite + audio cache, персист).

## Деплой / редеплой
```bash
# с локальной машины (после правок backend/):
rsync -az --exclude='.git' --exclude='.claude' --exclude='backend/.venv' \
  --exclude='backend/data' --exclude='frontend/node_modules' --exclude='__pycache__' \
  --exclude='.env' --exclude='.dockerignore' -e 'ssh -i ~/.ssh/antigravity_key' \
  ~/Documents/AI/Claude/english/ root@89.167.122.76:/root/english/
ssh -i ~/.ssh/antigravity_key root@89.167.122.76 \
  'cd /root/english && docker compose -p english -f docker-compose.deploy.yml up -d --build english_app'
```
- Фронт билдится **локально** (`npm run build`), на хост едет готовый `frontend/dist`
  (Dockerfile.deploy без node-стейджа — экономия RAM/диска на shared 4-проектном хосте).

## Кредлы
- `OPENAI_API_KEY` проброшен в `english_app` из `/root/english/.env` (perms 600).
  Источник — master `~/Documents/AI/Claude/.env`. См. `env_file_location.md` в auto-memory.
- `ENGLISH_APP_PASSWORD` (пароль входа) + `ENGLISH_COOKIE_SECRET` (`openssl rand -hex 32`,
  подпись cookie) тоже в `/root/english/.env`. Сменишь secret → у всех слетит логин.
- LLM: `ENGLISH_LLM_PROVIDER=auto` → на хосте резолвится в Meridian (172.17.0.1:3456).

## Safety rules
- **Shared prod host** (atmos/topanga/kai/la_cre/mme/sc/go контейнеры). Read-only by default.
  Никаких stop/rm/prune/restart чужих контейнеров. Свои — только `english_*`.
- **80/443 заняты `go_caddy`** (общий TLS-фронт хоста), :8000 занят `mme_backend` — поэтому
  english-стек на :8090, а HTTPS — через site-блок в go_caddy (см. Access points выше).
  Править go_caddy можно ТОЛЬКО аддитивно (свой блок) + `caddy reload`; чужие блоки не трогать.
- **Cost-bearing TTS за cookie-гейтом** — не снимать авторизацию (`ENGLISH_APP_PASSWORD`
  не оставлять пустым на хосте), не публиковать :8000 наружу. `/api/*` и `/audio/*` без
  cookie → 401; страницы → редирект на `/login`.
- С HTTPS (домен) Service Worker **регистрируется** (secure context) → install/offline работают.
  `main.tsx` сам решает: HTTPS → register `/sw.js`; HTTP → unregister + чистка кэшей (самолечение).

## Backup / disaster recovery
- Состояние целиком в volume `english_english_data` (SQLite + audio). Бэкап = `docker run --rm
  -v english_english_data:/d -v $PWD:/b alpine tar czf /b/english-data.tgz -C /d .`
- Откат: пересобрать из `/root/english` или передеплоить с локали (код — source of truth локально).
