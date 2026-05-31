# Active Context: english

> **Текущий фокус. Обновляется в КОНЦЕ каждой сессии.**

**Last updated:** 2026-05-31 (ночь-10)

## Current focus
**Реструктура тренировки в 3 последовательных урока — задеплоено на Hetzner**:
http://89.167.122.76:8090. Разрозненные экраны (Mnemonic / Training / BatchDetail) свёрнуты в
линейный flow на витрине-лестнице `BatchHome` (`batch/:id`): **Урок 1 — Мнемоническая основа**
(слушать историю, тапать якоря, мягкий пересказ → LLM-скор, БЕЗ хард-гейта), **Урок 2 — Фразы**
(якорь→фраза, перезапуск мнемо-истории прямо в уроке, Тест B drill, мягкий гейт mean≥6 из rotation),
**Урок 3 — Тесты** (история играет и на ~30% якорей замирает → назвать фразу вслух iOS-safe: аудио
пауза → тап по микрофону → resume; финал — пересказ всей последовательности = **хард-гейт** passed≥7
→ `l3_passed`). Запись микрофона ВЕЗДЕ строго по тапу (`RecFab`). Shared-инфра: `useMnemoAudio` хук
(все 3 урока, +`onEnded` callback), `RecFab`+`band()`, `lib/progress.ts` (localStorage-вехи).
Бэкенд: `scoring.py::_PHRASE_SYSTEM` теперь принимает сжатые/короткие формы как 9-10, если сохранены
суть и ключевой глагол (в Уроке 3 пользователю прямо разрешено «коротко»). **Playback оставлен**
(пассивное прослушивание из Library-hero — рабочая фича, не из консолидируемых тренировок).
Удалены вытесненные `BatchDetail.tsx`/`Mnemonic.tsx`/`Training.tsx` + роуты `/mnemo` `/train`.

## Recent changes (last 1-2 sessions)
- **3-урочная реструктура тренировки (2026-05-31 ночь-10):** консилиум (Opus+GPT+Claude) → flow из
  3 уроков вместо разрозненных тулов. `pages/BatchHome.tsx` (лестница, прогресс L2 живьём из rotation,
  L1/L3 из localStorage), `pages/Lesson1.tsx` (soft-пересказ через `scoreSequence`, без блокировки),
  `pages/Lesson2.tsx` (зоны якорь→фраза + «Переслушать историю» pill с karaoke `.lit`-подсветкой +
  Тест B adaptive rotation), `pages/Lesson3.tsx` (Stage-машина ready/running/exam; `onTick` пауза на
  выбранных якорях 30%, `onEnded`→exam; StopResult/ExamResult; хард-гейт). Shared: `audio/useMnemoAudio.ts`
  (+3-й параметр `onEnded`), `ui/RecFab.tsx`+`band`, `lib/progress.ts`. CSS: `.lesson-tag/.lesson-ladder/
  .lesson-card/.lc-*`, `.phrase-card.lit`, `.listening-note`+`.pulse-dot` (pulse-ring keyframe).
  Бэкенд `scoring.py`: `_PHRASE_SYSTEM` +правило «сжатая форма с ключевым глаголом = 9-10» + примеры
  (window→9, «walk me through it»→6). Проверено: `tsc -b` чисто, `npm run build` (55 модулей,
  266KB/84.5KB gzip), Claude_Preview прошёл Library→BatchHome→Урок1/2/3 без ошибок (консольный буфер
  показывал устаревшие HMR-ошибки `?t=...` — живой DOM чист). Деплой: rsync → пересборка `english_app`
  → контейнер свежий (started 06:28Z, image `0aca7ea25ca8`), бандл `index-Cz24b6pC.js` + новый
  `scoring.py` запечены и подтверждены `docker exec`-grep'ом, гейт `/api`→401. ✅
  ⚠️ E2E (реальное аудио/микрофон/random-stop/round-trip скоринга) headless не проверить — Лёша
  тестит на айфоне с паролем. ⚠️ rsync без `--delete` оставил на хосте старые `index-*.js` в dist —
  безвредно (index.html ссылается только на новый бандл).
- **Слой «Разделы» + 3-я вкладка (2026-05-30 ночь-9):** Лёша попросил добавить верхний слой
  «разделы Library» — где имеет смысл качать английский по доменам. Консилиум Opus+GPT (2 раунда,
  финал «+ Small Talk = 9») дал 9 разделов: live-tone (держит 3 бенча), pitch, negotiation,
  pressure, repair, leadership, requests, written, small-talk.
  - Backend: `models.Batch.section` (slug, index), `db.py _migrate` additive ALTER, `section` в
    list/detail (`routers/batches.py`), проброс через `schemas.BatchIn` + `content.py`
    (`BatchAuthor`→`to_batch_in`→`upsert`→`to_authoring`). `content/01-disagreement-ladder.json`
    получил `"section":"live-tone"`.
  - Frontend: `lib/sections.ts` (9 разделов, `SECTION_BY_SLUG`, `orderedSections`),
    `pages/Sections.tsx` (вкладка «Разделы»: `.sec-card` с обложкой 1-го батча/процедурным артом,
    счётчик или «Скоро»), `pages/SectionDetail.tsx` (грид батчей раздела, переиспользует `.album`),
    `App.tsx` 3-я вкладка + `secActive` (покрывает `/sections` и `/section/`), `IconSections`
    (слои), роуты в `main.tsx`, CSS-блок `.sec-*` в `index.css`.
  - Проверено в браузере (Claude_Preview, dev :5173 прокси на :8000): вкладка «Разделы» →
    live-tone «3 ›», 8× «Скоро»; клик → SectionDetail с 3 бенчами; нав остаётся на «Разделы».
    ⚠️ В превью был залипший SW со СТАРОЙ навигацией (Library/Playback/Profile) — снят
    unregister+caches.delete; на проде самолечение SW уже стоит (HTTP-деплой).
  - Деплой: `npm run build` → rsync (⚠️ `frontend/dist` сперва улетел в stray `/root/english/dist`
    — поправил отдельным rsync в `frontend/dist/` + убрал stray) → пересборка ТОЛЬКО `english_app`
    → миграция добавила колонку на старте → `docker exec` выставил всем 3 батчам `section=live-tone`.
    Гейт 303/401, контейнер Up, новый бандл `index-uMfcdzlq.js` в образе. ✅
  - В этот же деплой попал фикс **медленного аудио** из прошлой сессии: `mnemo.render_full` отдаёт
    MP3 (~450 КБ вместо ~1.4 МБ WAV, прогрессивное воспроизведение на iOS) + `Mnemonic.tsx`
    префетчит full-историю при загрузке батча (URL + warm HTTP-кэш) → первый тап «Вся история»
    мгновенный.
- **Single-voice мнемо-озвучка + вертикальный список фраз (2026-05-30 ночь-8):** двухголосый
  плейбек Лёше «очень плохо» (рвано, якоря в чужом тембре). Переписано:
  - `tts.py` — `synth`/`cache_key` принимают `instructions` (steering для `gpt-4o-mini-tts`;
    `gpt-4o` модели → `instructions`, иначе → `speed`). Кэш-ключ расширяется `i:{instructions}`
    только при наличии → существующий phrase-кэш стабилен.
  - `audio.py` — `render_session(..., model, instructions)` прокидывает их в `tts.synth`.
  - `mnemo.py` (НОВЫЙ) — `NARRATOR_VOICE="shimmer"`, `render_full(story)` = один steered pass
    (`INSTR`: один тёплый RU-нарратор, EN-слова в чистом American English тем же голосом, плавно).
    `generate_story(phrases, theme)` через `llm.chat` (V1-«гора» регистр) + `regenerate()` для
    пере-генерации story+spans любого батча.
  - `batches.py` — `mnemo_audio` переписан: `full` → `_lower_anchor_spans` (строчит ТОЛЬКО
    span-якоря для TTS, чтобы читал «read» а не «R-E-A-D»; дисплей не трогает) → `render_full` →
    `/audio/phrases/`; `anchors` → `_anchor_segments(gap=0.8)` → `render_session` → `/audio/sessions/`.
  - `Mnemonic.tsx` — якоря из `.chip`-грида (вёл на /play) в `.phrase-card` вертикальный список:
    номер+якорь+полная EN-фраза+своя play-кнопка (`player.playPhrase`/`prefetchPhrases`), gloss по
    тапу. `index.css` — добавлен `.pc-num`.
  - `content/01-disagreement-ladder.json` — `mnemo` = одобренный V1-текст со строчными якорями.
  - Проверено локально (spans 11/11; full 30.1s; anchors 22.3s/21 шагов; Drive-семплы Лёше),
    браузер (Playwright mobile 402×874 — вертикальные карточки по зонам, story внизу). Деплой:
    rsync → пересборка `english_app` → таргетный story+spans batch-1 (SRS сохранён) → full
    рендерится на проде (30.1s), контейнеры Up, Caddy 303→HTTPS. ✅
- **Scene-фото обложки (photo prompt v2, 2026-05-30 ночь-6):** pivot обратно к AI-обложкам, но
  как **реальное фото сцены мнемоники** (= `subtitle`) в едином жизнерадостном стиле (дневной свет,
  зелёная трава, голубое небо, человек со спины, без текста, 1:1). Промпт версионируется
  (`cover.py` v1 абстракция / v2 фото; откат = `ENGLISH_COVER_PROMPT_VERSION=1`, файлы `<slug>.v<N>.png`).
  `auto_cover=True` — обложка часть pipeline (fill-once). На проде перегенерены все 3.
- **Фикс «грузится старое» — кэш-заголовки + самолечащийся SW (2026-05-30 ночь-7):** Лёша с
  айфона видел старый UI/обложки, просил «тереть кукисы при каждом изменении UI». Диагноз: дело
  НЕ в куках (`eng_auth` = только логин) — это HTTP-кэш `index.html` (Starlette StaticFiles
  ставит ETag/Last-Modified, но НЕ Cache-Control → iOS Safari держит старый JS-бандл). Решено на
  уровне приложения, без ручных действий пользователя впредь: (1) `main.py` middleware
  `_cache_control` — `no-store, must-revalidate` для `/`, `/index.html`, `/sw.js`, `*.webmanifest`;
  `public, max-age=31536000, immutable` для `/assets/*` (Vite контент-хэширует → новый билд =
  новое имя); `no-cache` для `/covers/*` и `/audio/*` (ревалидация, чтобы перегенерённая обложка
  подхватилась). (2) `main.tsx` — SW регистрируется только в `isSecureContext`; по HTTP (IP-деплой)
  вместо регистрации сносит залипший SW (`getRegistrations→unregister`) + `caches.delete` (это
  #1 причина залипшей оболочки на PWA). Проверено локально curl-ом: `/`→no-store, `/assets/*`→
  immutable, `/covers/*`→no-cache. Задеплоено (rsync + пересборка только `english_app`), гейт
  401/303/200, контейнер Up. ⚠️ Текущий закэшенный `index.html` на айфоне Лёши был сохранён БЕЗ
  заголовка → один раз нужно вручную «Clear Website Data» в Safari (или hard-reload), дальше
  свежак подхватывается сам.
- **Scene-фото обложки v2 + версионирование промпта (2026-05-30 ночь-6):** Лёша: абстрактный арт
  «плохо выглядит, сложно ассоциировать» → нужно фото того, что происходит, в ОДНОМ стиле, с
  возможностью отката к текущему промпту. Сделано: (1) `cover.py` — реестр `PROMPT_VERSIONS`
  {1: абстракция (сохранена дословно), 2: фото}, активная версия из `cover_prompt_version`
  (config, default 2; env `ENGLISH_COVER_PROMPT_VERSION`). `build_prompt`/`generate_cover` берут
  версию + `subtitle` как сцену; файлы по версии `<slug>.v<N>.png` (откат = бесплатный кэш-свап).
  (2) v2-промпт: единый кинематографичный photo-стиль, человек со спины/без лица, без текста, 1:1.
  Первый вариант вышел «тёмный espresso, как Марс в апокалипсис» (Лёшина формулировка) → переписан
  на жизнерадостный: дневной свет, зелёная трава, голубое небо, оптимизм (снята жёсткая привязка к
  тёмной палитре приложения). (3) Pipeline: `content.upsert(auto_cover)` — fill-once генерация при
  загрузке батча (как title/subtitle), `auto_cover=True` в config; paste-commit генерит в фоне
  (`_gen_cover_bg` теперь с subtitle), не блокируя HTTP; CLI `app/gencovers.py` (`--all/<id>/
  --force/--version`). (4) Фронт: `ui/Art.tsx::BatchCover` (фото + fallback на процедурный
  `BatchArt` при отсутствии/ошибке), вписан в Library hero+грид, BatchDetail, мини-плеер; CSS
  `.bcover{object-fit:cover}`. На проде перегенерены все 3 (`gencovers --all --force`, ~$0.50):
  #1 восхождение, #2 раскопки, #3 выступление — все в зелёно-голубом дневном свете. Гейт
  401/401/303/303/200 (covers тоже за гейтом). ⚠️ Тест-генерации #1 шли локально (2× ~$0.17).
- **Образ-подписи мнемоник + счётчик фраз на карточках (2026-05-30 вечер):** подпись = образ
  мнемоники в 1–3 слова (что за сцена/место/метафора), не пересказ. `titling.suggest_subtitle`
  (читает ТОЛЬКО текст мнемоники — theme намеренно игнор, т.к. метафора темы расходится с образом
  истории: «лестница» темы над «горой» мнемоники). Встроено в pipeline `content.upsert(auto_subtitle/
  force_subtitle)` — все 3 пути создания (load_path, /imports/commit, /imports/upsert). CLI
  `app/resubtitle.py` (бэкфилл, зеркало retitle). `_preview` больше НЕ режет 1-ю фразу истории
  (subtitle → theme). Фронт: `.album-meta` (`N PATTERNS`) на гриде, у hero уже был. На проде:
  #1 «Восхождение на гору», #2 «Раскопки», #3 «Выступление на сцене» (Meridian/claude-sonnet).
  Гейт подтверждён 401/401/303/200. ⚠️ SW не кэширует на HTTP/IP — у пользователя обновится сразу
  (локально на localhost SW регистрируется → ловил stale-кэш, снимается unregister+caches.delete).
- **Essence-названия батчей + фикс синих заголовков (2026-05-30 день):** название = СУТЬ фраз
  (что позволяют делать в разговоре), не мнемо-метафора. `app/titling.py` (`suggest_title` через
  `llm.chat`, sentence-case фикс), `content.upsert(auto_title/force_title)`, CLI `app/retitle.py`.
  Встроено в pipeline: новые батчи авто-титулуются (Meridian/claude-sonnet). На проде:
  #1 «Несогласие с нарастающей прямотой», #2 «Запрос мнения собеседника», #3 «Побуждение к
  откровенности». Фикс: `.album-title` без `color` → iOS рендерил синий → добавлен `var(--text)`.
- **Title-hero редизайн + content pipeline (2026-05-30 ночь-5):** два запроса Лёши —
  (1) понятный pipeline загрузок/корректировок + достроить БД; (2) дизайн-pivot «заголовок-герой,
  арт поддерживающий, убрать синий, осмысленные мнемо-превью, единый абстрактный арт».
  - Backend: `content.py` (`BatchAuthor`/`PhraseAuthor` → `to_batch_in` деривит order_index/
    intensity/zone-order/spans → `upsert` create-or-replace by slug, wipe+rewrite children,
    preserve id+cover; `to_authoring` round-trip export). Эндпоинты `/imports/upsert`,
    `/imports/seed`, `GET /batches/{id}/export`. Seed-CLI `app/seed.py`. Колонка `batch.subtitle`
    (db.py `_migrate` additive ALTER, schemas `BatchIn.subtitle`). `auto_cover=False`.
    `batches.py` list отдаёт `subtitle` + `_preview()` (subtitle → 1-я фраза истории → theme).
  - Frontend: `ui/Art.tsx` (`BatchArt` процедурный SVG), `lib/accent.ts` → единый `INK`.
    Library/BatchDetail/App переписаны на title-hero + арт-полосу, `ui/Cover.tsx` удалён.
    CSS: `--accent:#26211B`, `--mark:#9A7B4F` (де-blue), `.bart/.feature/.album/.detail-art`.
  - Проверено в браузере (Claude_Preview 375×812): Library/Detail/Mnemonic/Playback — все 4
    требования выполнены, синего нет, spans (11 якорей) резолвятся, плеер играет. ✅
  - Редеплой: `npm run build` локально → rsync → пересобран ТОЛЬКО `english_app` (caddy не тронут) →
    `docker exec english_app python -m app.seed` (батч 1 updated in place, id=1, mnemo 258, 11 фраз).
    Гейт подтверждён: `/api`→401, `/audio`→401, `/`→303, `/login`→200. ✅
  - Открыто: батчи 2/3 (slug `batch-2/3`) без кураторского subtitle (превью из 1-й фразы);
    мелкий CSS-nit на Mnemonic — нет пробела `ThemeЛестница…` в about-таблице.
- **AI cover-art система (2026-05-29 ночь-4):** генерация премиум-обложек через OpenAI Images
  (gpt-image-1, 1024², quality=high, ~$0.167/шт). Backend: `cover.py` (метафоры по ключевым
  словам темы + editorial-промпт), миграция `cover_path` (db.py `_migrate`, additive ALTER),
  `/covers` StaticFiles-mount за cookie-гейтом, POST `/api/batches/{id}/cover`, авто-генерация
  фоном при импорте (`auto_cover=True`). Frontend: `ui/Cover.tsx` (`BatchCover` с gradient-
  fallback на onError), Library redesign (доминантный `.feature` hero 4/5 + `.album` грид),
  BatchDetail `.detail-art`, mini-player cover. `vite.config.ts` — добавлен прокси `/covers`.
  - ⚠️ **Промпт-урок:** первая попытка «light, airy, minimal, negative space» дала вымытую
    пастель (Headspace). Переписал на «rich, deep, dramatic volumetric light, high contrast,
    dark moody» + метафоры с «powerful/intense» вместо «quiet/gentle» → насыщенные album-covers.
  - 3 обложки сгенерены: Восхождение (золотой восход света), Раскопки (раскол с раскалённым
    ядром), Сцена (театральный сноп света). Проверено в браузере (Claude_Preview 375×812):
    hero + грид + BatchDetail. ✅
  - Редеплой: rsync → пересобран ТОЛЬКО `english_app` (caddy Up 5h, не тронут). Обложки
    сгенерены на проде через `docker exec ... cover.generate_cover` (минуя HTTP-гейт). Гейт
    подтверждён post-deploy: без cookie `/api`→401, `/`→303→`/login`, `/covers/*`→303; с cookie
    `/api/batches`→200 (все 3 отдают `cover_url`), `/covers/*.png`→200 image/png. ✅
- **Плеер-фиксы по iPhone-фидбеку (2026-05-29 ночь-3):** Лёша прислал скриншот Playback с 4 багами.
  Все 4 исправлены, проверены в браузере (Claude_Preview, mobile 375×812) и залиты на Hetzner.
  1. **Shuffle «не нажимался» (сбрасывал экран)** — `reshuffle` перезапускал сессию с `autoplay=true`,
     но не сохранял факт что играли, и всегда стартовал с нуля. Переписан как тумблер
     `full_random ↔ ordered` с `wasPlaying`-сохранением воспроизведения (PlayerContext.tsx:169).
  2. **Loop** — проверен: native `audio.loop` на цельном session-WAV, тумблер работает (true↔false).
  3. **Loop + Shuffle ON по умолчанию** — `loop` initial `false→true`, `order` initial
     `ordered→full_random` (PlayerContext.tsx:70,77); `playBatch`/Library hero тоже `full_random`.
  4. **Фраза играла дважды** — `Setting.listening_repeats 1→0`, `default_order_mode→full_random`
     (models.py). ⚠️ model-default бьёт только новые строки → существующий Setting row (id=1)
     в local+prod обновлён через `PUT /api/settings`. Listening-рендер: каждая фраза один раз.
  - Редеплой: пересобран ТОЛЬКО `english_app` (caddy не трогали, Up). Auth gate подтверждён
    post-deploy (/ → 303, /api → 401). ⚠️ Новые хеши `dist/assets/index-CgII8uGH.js` — айфону
    нужен reload страницы / PWA, чтобы подхватить новый фронт.
- **Премиум-редизайн фронта (2026-05-29 ночь):** полностью переписан UI под Product Vision.
  Светлая дизайн-система (bg #F8F8F6 / card #FFF / text #111 / 5 accent-палитр по батчам),
  SF Pro, доминантные anchor-глаголы. 6 экранов: Library (hero Current Focus + 2-col grid),
  Batch Detail, **Phrase Playback** (Apple-Music-lyrics: гигантский anchor + scrub + transport
  + pattern-list с plan-driven подсветкой), Mnemonic, Profile, Settings/Import (рестайл).
  Глобальный персистентный плеер (PlayerContext + один `<audio>`) переживает смену роутов;
  мини-плеер + нижняя навигация Library/Playback/Profile.
  - Новые файлы: `src/lib/accent.ts`, `src/player/PlayerContext.tsx`, `src/ui/icons.tsx`,
    `pages/{Library,BatchDetail,Playback,Mnemonic,Profile}.tsx`. Удалены старые
    BatchPage/BatchList/Player/MnemoView (логика мигрировала в экраны + PlayerContext).
  - **Bug fix**: мини-плеер уезжал за правый край — keyframe `fade-up` затирал
    `translateX(-50%)`. Введён keyframe `mini-rise` (сохраняет центрирование). index.css:60.
  - Login-страница (`backend/app/main.py`) ребрендирована + переведена на светлую премиум-тему.
  - Проверено в браузере (Claude_Preview, mobile 375×812): golden path Library→Detail→Playback
    с реальной TTS-сессией — gapless-аудио играет, lyrics-подсветка следует за плеем. ✅
  - Редеплой: rsync `frontend/dist` + `backend/app` → `docker compose -p english up -d --build
    english_app` (только app, caddy не трогали). Cookie gate подтверждён (/ → 303 /login,
    /api → 401), новый login title «English Executive — вход». ✅
- Мобильная вёрстка проверена; мелкие фиксы PWA-meta.
- Деплой на Hetzner по IP (порт 8090, т.к. 80/443 у go_caddy, :8000 у mme). Контейнеры
  `english_app` + `english_caddy`, `-p english`, код `/root/english`, volume `english_english_data`.
  Фронт собирается локально → на хост едет готовый `dist` (Dockerfile.deploy, без node).
- **Исправлен P0-баг**: OpenAI tts-1 отдаёт streaming-WAV с placeholder-размерами
  (data=0xFFFFFFFF) → битый nframes ломал сборку gapless-WAV (uint32 overflow). Фикс в
  `audio.py` (не копировать nframes) + `tts.py` (длительность по факту). Проверено на хосте:
  recall/listening рендерятся, аудио с HTTP Range. Кэш прогрет.

## Next steps
- [x] **Импорт реальных RU-original батчей** — DONE (2026-05-29 ночь-2). «Раскопки» (9 фраз)
      и «Сцена» (8 фраз) залиты в local + prod (Hetzner). На хосте 3 батча: Восхождение(5),
      Раскопки(9), Сцена(8). По «Сцене»: Pause без EN-фразы → заглушка `(stay silent)`;
      зоны Mechanical/Warm/Presence — мои имена под шкалу харизмы, Лёша может переименовать.
- [x] **Прогрев аудио-кэша для новых батчей** — DONE (2026-05-29 ночь-2). Прогнаны
      listening-сессии на хосте (Раскопки 60.3с, Сцена 68.2с) → per-phrase TTS-кэш по всем
      EN-фразам прогрет. Проверка: recall-рендер обоих за 0.06-0.07с (cache hit, ноль трат).
      Первый тап с айфона по Раскопкам/Сцене — мгновенный в обоих режимах.
- [ ] **iOS-тест на реальном iPhone** (идёт сейчас): фоновое аудио (заблокированный экран /
      свёрнутый Safari), Media Session на локскрине, перемотка. P0-риск из челленджа.
      ⚠️ PWA Service Worker по HTTP не регистрируется (insecure) → offline/install не
      проверить по IP; для этого нужен домен+HTTPS.
- [ ] Оценить качество tts-1 / паузы / RU-стимул вживую, при необходимости подкрутить
      `recall_gap_*` в Настройках.
- [ ] Если зайдёт — домен + HTTPS (тогда заработает полноценный PWA/offline) вместо raw IP.
- [ ] v0.2: Режим Контекст (генерация через Meridian + approval gate), ffmpeg WAV→MP3.
- [x] **Мнемо-рассказ: озвучка + раскладки full/anchors** — DONE и ЗАДЕПЛОЕНО (2026-05-30
      ночь-8). Первая версия была двухголосой (RU-нарратор + EN-якоря другим голосом) → Лёше
      «очень плохо» → переписана на **single-voice single-pass** (shimmer, `gpt-4o-mini-tts` +
      code-switching `instructions`) + вертикальный список фраз на экране Mnemonic. Детали —
      в Recent changes выше. Якоря-чипы заменены на карточки (якорь + полная EN-фраза + play).
- [x] **Батчи 2/3 приведены к V1-формату** — DONE (2026-05-30 ночь-8). Их истории УЖЕ были
      связными V1-нарративами (раскопки / сцена — совпадают с обложками), отличались только
      UPPERCASE-якорями. Регенерацию через LLM НЕ делал (риск: новая история разойдётся с
      обложкой). Вместо этого — детерминированно строчны только якоря (`_lower_anchor_spans` →
      пере-расчёт spans, позиции не меняются): batch-2 9/9, batch-3 8/8, без warnings. Аудио
      прогрето на проде (full + anchors). Все 3 батча теперь единообразны: single-voice shimmer,
      строчные якоря, вертикальный список фраз. ⚠️ У 2/3 нет `content/` JSON — prod DB = источник.

## Open questions
- Блоки 10-20 мин vs один длинный WAV — решить на реальном устройстве.
- Длительности пауз (think=4с, after=2с) — комфортны ли вживую.
- Нужен ли домен (HTTPS+PWA) или raw-IP достаточно для личного использования.

## Blockers
- Фоновое аудио iOS финально проверяется только на айфоне Лёши (идёт сейчас).
- Полноценный PWA (offline/install) недоступен по HTTP/IP — нужен HTTPS+домен.
