# Architecture: english (Executive English аудио-тренажёр)

> **Component map and dependencies. Updates on major refactors.**
> Полное ТЗ: `TZ-portal.md` (v1). Дизайн-источник: `_inbox/challenge-2026-05-29-0035.md`.

## Top-level diagram

```
                    ┌─────────────────────────────────────┐
   iPhone (PWA)     │   Frontend: React+Vite PWA           │
   наушники, метро  │   - Active Recall player (DEFAULT)   │
   экран заблокир.  │   - Listening drill / Mnemo view     │
        │           │   - <audio> single element           │
        │           │   - Service Worker + Cache API       │  offline
        │  HTTPS     │   - Media Session API (lock screen)  │
        ▼           └───────────────┬─────────────────────┘
   ┌─────────┐                      │ REST/JSON + /audio/*.wav (static)
   │  Caddy  │  auto-HTTPS          ▼
   │ basic-  │   ┌──────────────────────────────────────────┐
   │  auth   │──▶│  Backend: FastAPI (Docker, Hetzner)      │
   └─────────┘   │  routers: batches / imports / sessions / │
                 │           settings / audio               │
                 │  importer.py  (deterministic + LLM fb)   │
                 │  llm.py       (provider abstraction)     │──▶ Meridian (Hetzner)
                 │  tts.py       (OpenAI TTS + disk cache)  │──▶ OpenAI TTS
                 │  audio.py     (gapless WAV render, pure  │
                 │               python; ffmpeg optional)   │
                 └───────┬───────────────────┬──────────────┘
                         │                   │
                   ┌─────▼─────┐       ┌─────▼──────────────┐
                   │ SQLite    │       │ /data/audio        │
                   │ (WAL)     │       │  phrases/*.wav     │
                   │ /data/    │       │  sessions/*.wav    │
                   │  app.db   │       │ /data/exports/*.json│
                   └───────────┘       └────────────────────┘
```

## Components

| Компонент | Роль | Технология |
|---|---|---|
| Frontend PWA | Mobile-first плеер + admin; offline; lock-screen audio | React 18 + Vite + TS, vanilla SW |
| Backend API | REST, бизнес-логика, рендер аудио | FastAPI (Python 3.12), SQLModel, Pydantic v2 |
| DB | Источник истины (батчи/фразы/мнема/SRS) | SQLite + WAL |
| importer | Сырой текст → строгий JSON (детерминированный парсер, LLM-фолбэк) | regex + llm.py |
| llm | Провайдер-абстракция parse/generate/repair | Meridian / Anthropic-direct / OpenAI |
| tts | Озвучка + дисковый кэш по богатому хэшу | OpenAI tts-1, формат WAV (MVP) |
| audio | Gapless session render (паузы зашиты в файл) | pure-python `wave` concat; ffmpeg опц. для MP3 |
| Caddy | reverse-proxy, HTTPS, basic-auth | Caddy |

## External dependencies
- **OpenAI TTS** (`tts-1`/`tts-1-hd`) — ключ `OPENAI_API_KEY` из master `.env`. Биллинг по входным символам.
- **Meridian** (`172.17.0.1:3456`, Hetzner-only) — дефолтный LLM-провайдер для parse/generate. Локально недоступен → фолбэк на Anthropic-direct (`ANTHROPIC_API_KEY`/`ANTHROPIC_BASE_URL`) или OpenAI.
- **ffmpeg** — опционально (только для пост-сжатия WAV→MP3). В Docker присутствует; локально нет.

## Data flow

### Import (paste → JSON → approve → save)
1. Пользователь вставляет сырой текст батча → `POST /imports/parse`.
2. `importer.parse()`: сначала **детерминированный парсер** формата `N. Keyword → phrase` + блок `Мнемо-текст:`. Если формат не распознан → **LLM-фолбэк** (`llm.parse_batch`) возвращает тот же JSON.
3. Вычисляются **spans** якорей в `story_ru`: для каждого keyword ищется его вхождение (с учётом регистра/капса) → `{anchor_id, phrase_id, start, end}`. Неоднозначности (повтор слова) → помечаются для ручной правки.
4. Ответ — preview JSON (валидируется Pydantic-схемой) + список предупреждений.
5. Пользователь правит в UI → `POST /imports/commit` → запись в SQLite, `status=approved`. **LLM по сохранённому JSON больше не ездит.**

### Audio session render (gapless)
1. `POST /sessions` с `{batch_id, mode, order_mode}` → строится **plan** (список сегментов с длительностями пауз).
2. Для каждого нужного текста → `tts.synth()` (кэш-хит по хэшу или вызов OpenAI), сохранение `phrases/<hash>.wav`.
3. `audio.render_session(plan)` → конкатенация PCM (pure python `wave`) с вставкой тишины (нули) между сегментами → один `sessions/<id>.wav`.
4. Ответ — URL сессии + plan_json (для подсветки на клиенте по таймкодам).
5. Клиент скачивает WAV в **Cache API** → играет офлайн одним `<audio>`.

### Active Recall plan (DEFAULT режим)
Для каждой фразы сегменты: `[RU-стимул (gloss/scenario) TTS] → silence 4s → [EN phrase TTS] → silence 2s → [EN phrase TTS повтор] → gap 1.5s → next`. Всё в одном WAV → паузы переживают блокировку экрана iOS (нет JS-таймеров).

### Listening plan (вспомогательный)
`[EN phrase TTS] → gap → (repeat) → gap → next`. Порядок: ordered / zone-random / full-random.

## Известные ограничения / weak spots (MVP)
- **iOS фон реально не проверить без устройства** — рендерим gapless WAV именно чтобы обойти JS-таймеры; финальная валидация — на айфоне Алексея.
- **WAV тяжёлый** (~3 МБ/мин). MVP: ок для одного юзера. v0.2: ffmpeg WAV→MP3 в Docker (3-10× меньше) для offline-кэша.
- **spans для повторяющихся слов** — детерминированный парсер берёт первое вхождение + warning; ручная правка обязательна для коллизий.
- **Meridian только на Hetzner** — локальный import использует детерминированный парсер (LLM не нужен для known-формата) либо Anthropic-direct.
- **Стоимостные эндпоинты не публикуются** — TTS/генерация гоняются из admin/cron, наружу только статика + плеер (см. TZ §10).

## Layout
```
english/
  backend/  app/{config,db,models,schemas,importer,llm,tts,audio,main}.py
            app/routers/{batches,imports,sessions,settings,audio}.py
            data/  (sqlite + audio, gitignored)
  frontend/ src/{pages,audio,api}  public/{manifest,sw.js}
  Dockerfile  docker-compose.yml  Caddyfile  .gitignore
```
