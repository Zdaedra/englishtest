# Progress Log: english

> **Append-only changelog. Новые записи сверху.**

---

## 2026-05-31 — Урок 2: вернул плеер шаффл-луп + переделал проверку фраз

- **Запрос Лёши (по скриншотам с телефона):** (а) «у тебя пропал классный плеер… верни сюда —
  один из основных элементов: учим-учим-учим, потом просим проиграть ВСЕ фразы шаффл-луп»;
  (б) проверка фраз непонятна — «из интерфейса не следует, что это запускает микрофон и
  воспроизведение», ловил 0/10 «тишина».
- **Плеер (`Lesson2.tsx`):** новая секция **«3 · Слушай все фразы»** с заметной кнопкой
  «▶ Слушать вперемешку» → `player.playBatch(batch, {mode:"listening", order:"full_random"})`
  + `nav("/play")` (тот же вход, что hero в Library). Стоит после блока «Якорь → фраза».
- **Проверка фраз → «4 · Проверь фразы» (перенумерована):** (1) экран-старт с кнопкой
  «Начать проверку» + пояснением, что включится микрофон и звук; (2) подсказка на слух —
  при входе на карточку фраза авто-проигрывается (`drillStarted`+`lastHintRef` дедупит по
  phrase_id) + кнопка «▶ Прослушать ещё раз»; (3) понятные подписи микрофона:
  «Нажми и говори» → «Идёт запись — нажми «стоп»» → «Проверяем…» (было просто «Запись»);
  (4) защита от тишины: clip.ms<600 или пустой transcript → «Не расслышал…», не 0/10.
- **Урок 3 (`Lesson3.tsx`):** те же подписи микрофона + guard от тишины в обоих местах
  (стоп-проверка и финальный экзамен) — для единообразия.
- **Пед-логика:** L2 = заучивание (shadow: услышал фразу → повтори), поэтому подсказка на
  слух уместна; жёсткий тест по памяти живёт в L3.
- **Деплой:** rsync + пересборка `english_app`. Проверено в preview (mobile 375px, все секции
  рендерятся/кликаются) и на проде — index.html отдаёт новый бандл `index-D3Pn_226.js`,
  контейнер пересоздан. ✅

---

## 2026-05-31 — Фикс финального экзамена: gpt-4.1-nano → mini (был провал скоринга)

- **Симптом (Лёша, первый живой прогон по HTTPS):** в Уроке-пересказе сказал ВСЕ якоря (RU+EN
  вперемешку), а получил **4/10**, все 10 якорей помечены «забыл», порядок «нарушен».
- **Диагностика по БД (`sequenceattempt.transcript`):** STT отработал отлично — транскрипт
  содержит `understand, walk, read, far, push, outlier, why, straight` ДОСЛОВНО + «hesitate»
  (≈hesitation) и «ленд» (≈land, транслитерация). Виноват не STT и не фронт, а **скорер**:
  `via=llm`, модель **gpt-4.1-nano** пометила дословно присутствующие якоря пропущенными.
- **Эмпирическая проверка** (тот же payload, temp 0): nano→4/10 (6 ложных пропусков);
  **gpt-4.1-mini→9/10**, пропусков нет, порядок ок; gpt-4o-mini→10/10. Вывод: nano слишком
  слаба для кросс-язычного пересказа с транслитерациями — а это ЖЁСТКИЙ ГЕЙТ.
- **Фикс (`scoring.py`):** разнесли модели. `SCORING_MODEL="gpt-4.1-nano"` остаётся для частого
  фразового дрилла (Test B, есть локальный гейт на дословность). Новый
  `SEQUENCE_MODEL="gpt-4.1-mini"` для экзамена (Test A) — зовётся раз на батч, цена ничтожна.
  `_openai_json` получил параметр `model=`; `score_sequence` передаёт `SEQUENCE_MODEL`.
- **Деплой:** rsync + пересборка только `english_app`. Проверено В КОНТЕЙНЕРЕ живым прогоном
  `score_sequence` на реальном транскрипте → **9/10**, missed только `hesitation` (сказал
  «hesitate»), order_ok=True, passed. ✅

---

## 2026-05-31 — HTTPS на executive-english.net (микрофон заработал на телефоне)

- **Симптом (Лёша, iPhone):** в Уроке «этот браузер не умеет записывать звук — откройте в
  Safari/Chrome», хотя уже Safari. **Корень:** сайт открыт по голому HTTP (`No seguro —
  89.167.122.76:8090`). Браузеры дают доступ к микрофону только в **secure context** (HTTPS/
  localhost) → по HTTP `navigator.mediaDevices === undefined` → `useRecorder.supported=false`.
  Весь голосовой флоу (записи во всех 3 уроках) был мёртв на телефоне. Не баг Safari/кода —
  правило безопасности браузера.
- **Решение — HTTPS через общий go_caddy.** Порты 80/443 на shared-хосте держит `go_caddy`
  (исторически из kai-go, де-факто общий TLS-фронт: обслуживает kai + atmos). Свой `english_caddy`
  встать на 80/443 не может. Вписались в существующий: добавлен site-блок в
  `/root/go_lesson_mvp/docker/Caddyfile`:
  `executive-english.net { reverse_proxy 89.167.122.76:8090 }`. Бэкап файла сделан перед правкой.
  `caddy validate` → OK, `caddy reload` — бесшовно (kai/atmos остались 200).
- **DNS:** Лёша добавил на Squarespace A-запись `@ → 89.167.122.76` (домен `executive-english.net`,
  Squarespace, NS Google Domains, активен до 2027; старые парковочные записи убраны — все 4
  авторитетных NS отдают только наш IP).
- **Проверено:** `https://executive-english.net` → Let's Encrypt cert (CN=executive-english.net,
  до 29 авг 2026, авто-renew), `303 → /login` (cookie-гейт жив), HTTP→HTTPS 308-редирект,
  HTTP/2 + h3. Соседи kai-go.com / book.atmos-steam.com / admin.trypranaextract.com → 200.
- **Бонусы HTTPS:** теперь `window.isSecureContext=true` → `main.tsx` регистрирует Service Worker
  (PWA install/offline). Канонический URL стал `https://executive-english.net` (см. accessAndSafety).
- **Осталось за Лёшей:** открыть на iPhone https://executive-english.net, залогиниться, дать
  доступ к микрофону и прогнать запись в Уроках 1/2/3 (E2E голос+скоринг).

---

## 2026-05-31 (ночь-10) — Реструктуризация в 3 чётких урока + деплой

- **Запрос Лёши (по итогу консилиума):** прежний разрозненный flow (Mnemonic / Training /
  Playback) свести к **3 последовательным урокам** на батч, с понятной прогрессией и одним
  жёстким гейтом в конце.
  - **Урок 1 — Мнемоническая основа:** слушать RU-историю с EN-якорями, тапать якоря (раскрыть
    фразы), затем мягкий пересказ вслух → LLM-оценка. **Без жёсткого гейта** (Лёша выбрал «мягкий
    gate (рекомендация)»).
  - **Урок 2 — Фразы:** учить фразы на якорях; play по фразе + tap-to-reveal gloss; **возможность
    перезапустить мнемо-историю прямо внутри Урока 2**; финал — дрилл Test B (адаптивная ротация);
    мягкий гейт (mean≥6).
  - **Урок 3 — Тесты:** мнемо-история играет и на случайных ~30% якорей замирает → ученик
    называет фразу вслух → LLM-оценка; затем **финальный пересказ-последовательность = жёсткий
    гейт** (passed≥7 ставит `l3_passed`). iOS-safe random-stop: аудио ПАУЗИТСЯ, ученик тапает мик
    в foreground-жесте, продолжение по тапу.
- **Frontend:** новый `pages/Lesson3.tsx` (stage-машина ready/running/exam; `onTick` пауза на
  концах выбранных якорей; `onEnded`→exam; `sampleSorted` берёт ~30% якорей; `onMicStop`→
  scorePhrase, `onMicExam`→scoreSequence; tap-only мик через `RecFab`). `main.tsx` += импорт+роут
  `batch/:id/lesson/3`; убраны мёртвые роуты `batch/:id/mnemo` и `batch/:id/train` (+ их импорты).
  `useMnemoAudio` получил 3-й параметр `onEnded?`. `index.css` += блок `.listening-note` +
  `.pulse-dot` + `@keyframes pulse-ring` (idle-состояние между стопами; bronze `--mark`
  rgb 154,123,79). **Удалены** orphaned-страницы `BatchDetail.tsx`, `Mnemonic.tsx`, `Training.tsx`.
  **Оставлен** Playback (вкладка + MiniPlayer): Library-герой «Текущий фокус» линкует на `/play`
  (`player.playBatch(... mode:"listening"...)`) — это живой вход, не мёртвый код.
- **Backend `scoring.py`:** `_PHRASE_SYSTEM` теперь принимает **сжатые/укороченные формы** как
  9-10 (если сохранены суть и ключевой глагол/действие); снижение до 6-7 только если потеряно
  смыслонесущее слово, не за краткость. Обновлены примеры: «the window is open»→9,
  «walk me through it»→6, «here is what is at stake»→9. Структура файла не менялась.
- **Деплой (Frontend + Backend, одобрено Лёшей):** `npm run build` → rsync на Hetzner →
  пересборка ТОЛЬКО `english_app` (caddy не тронут). Проверено В КОНТЕЙНЕРЕ: контейнер свежий
  (StartedAt 2026-05-31T06:28:29Z, образ sha256:0aca7ea25ca8), бандл `index-Cz24b6pC.js` с
  «Начать тест», `scoring.py` содержит «КОРОТКО», «walk me through it»→6, «the window is open»→9;
  гейт `/api`→401. ✅ ⚠️ rsync без `--delete` оставил stale старые `index-*.js` в host dist —
  безвредно (index.html ссылается только на новый бандл).
- **Открыто (не блокирует):** E2E на реальном iPhone (аудио/мик/random-stop/scoring round-trip —
  только Лёша, нужен пароль гейта); возможный домен+HTTPS для PWA; возможный v0.2 Context mode.

---

## 2026-05-30 (ночь-9) — Слой «Разделы» (Library sections) + 3-я вкладка

- **Запрос Лёши:** добавить верхний слой «разделы Library» — домены, где имеет смысл качать
  английский; «бизнес-харизма» = один из них (в нём текущие 3 бенча). Просил консилиум Opus+GPT
  найти ~6-7 разделов + второй раунд критики на покрытие. Итог — **9 ситуативных разделов**:
  live-tone (держит 3 бенча), pitch, negotiation, pressure, repair, leadership, requests, written,
  small-talk.
- **Backend:** `models.Batch.section` (slug, index); `db.py _migrate` — additive ALTER (колонка
  на старте, дефолт `""`); `section` в list/detail API (`routers/batches.py`); проброшен через
  `schemas.BatchIn` и `content.py` (`BatchAuthor`→`to_batch_in`→`upsert` обе ветки→`to_authoring`).
  `content/01-disagreement-ladder.json` += `"section":"live-tone"`.
- **Frontend:** `lib/sections.ts` (статичная мета 9 разделов: slug/EN/RU/blurb/order +
  `SECTION_BY_SLUG`/`orderedSections`); `pages/Sections.tsx` (вкладка «Разделы», `.sec-card` с
  обложкой 1-го батча или процедурным `BatchArt`, счётчик `N ›` или бейдж «Скоро»);
  `pages/SectionDetail.tsx` (грид батчей раздела, переиспользует `.album`); `App.tsx` — 3-я
  вкладка, `secActive` (покрывает `/sections` + `/section/`); `IconSections` (слои); роуты
  `/sections` + `/section/:slug` в `main.tsx`; CSS-блок `.sec-*` в `index.css`.
- **Проверено в браузере** (Claude_Preview, vite dev :5173 прокси на uvicorn :8000): вкладка
  «Разделы» → live-tone «3 ›», 8× «Скоро»; клик → SectionDetail с тремя бенчами; навигация
  остаётся на «Разделы». ⚠️ В превью был залипший SW со старой навигацией (Library/Playback/
  Profile) — снят unregister + caches.delete; на проде самолечение SW уже стоит (HTTP-деплой).
- **Деплой:** `npm run build` → rsync (поймал баг: `frontend/dist` как источник улетел в stray
  `/root/english/dist`; поправил отдельным `rsync frontend/dist/ → frontend/dist/` + удалил stray)
  → пересборка ТОЛЬКО `english_app` (caddy не тронут) → миграция добавила колонку на старте →
  `docker exec english_app python` выставил всем 3 батчам `section='live-tone'`. Гейт 303(`/`)/
  401(`/api`), контейнер Up, образ содержит новый бандл `index-uMfcdzlq.js`. ✅
- **Прицепом** в этот деплой попал фикс медленного аудио из прошлой сессии: `mnemo.render_full`
  отдаёт MP3 (~450 КБ вместо ~1.4 МБ WAV) + `Mnemonic.tsx` префетчит full-историю при загрузке
  батча → первый тап «Вся история» мгновенный.

---

## 2026-05-30 (ночь-7) — Фикс «грузится старое»: кэш-заголовки + самолечащийся Service Worker

- **Запрос Лёши (айфон):** видит старый UI/обложки, сформулировал как «давай тереть кукисы при
  каждом изменении UI». Реальная причина — НЕ куки (`eng_auth` — только логин-сессия), а HTTP-кэш
  `index.html`: Starlette `StaticFiles` ставит ETag/Last-Modified, но НЕ `Cache-Control`, поэтому
  iOS Safari эвристически держит старый HTML → тянет старый контент-хэшированный JS-бандл → старый UI.
- **Backend `main.py`:** добавлен `@app.middleware("http") _cache_control` (внутренний слой
  относительно `_auth_gate`):
  - `/`, `/index.html`, `/sw.js`, `*.webmanifest` → `no-store, must-revalidate` (точка входа
    никогда не кэшируется → деплой всегда виден).
  - `/assets/*` → `public, max-age=31536000, immutable` (Vite контент-хэширует имена → новый билд
    = новый файл, кэшировать вечно безопасно и быстро).
  - `/covers/*`, `/audio/*` → `no-cache` (разрешает ревалидацию по ETag, чтобы перегенерённая
    обложка/переснятый клип подхватились даже при том же имени).
- **Frontend `main.tsx`:** SW регистрируется только при `window.isSecureContext`. По HTTP (IP-деплой
  SW и так заблокирован) вместо регистрации — самолечение: `getRegistrations().then(unregister)` +
  `caches.keys().then(delete)`. Это снимает «залипшую оболочку» — #1 причину stale-UI на PWA, если
  SW когда-либо зарегистрировался (например на localhost).
- **Проверка локально (curl, гейт выключен):** `/`→`no-store, must-revalidate`,
  `/assets/index-*.js`→`immutable`, `/sw.js`+`/manifest.webmanifest`→`no-store`,
  `/covers/*`→`no-cache`. (HEAD на `/api/*`→404 — предсуществующее поведение FastAPI, GET→200.)
- **Деплой:** `npm run build` (новый `index-DzlJnE5f.js`) → rsync → пересобран ТОЛЬКО `english_app`
  (caddy/чужие контейнеры не тронуты). Прод: `/api/health`→401, `/`(без куки)→303 `/login`,
  `/login`→200, контейнер Up. Значения заголовков на самом `index.html` — за гейтом (всё кроме
  `/api`,`/audio` без куки редиректит на `/login`), но код идентичен локально проверенному.
- **⚠️ Разовый шаг для Лёши:** текущий `index.html` уже лежит в кэше айфона БЕЗ заголовка → один раз
  нужно вручную «Clear Website Data» в Safari (или hard-reload). Дальше — автоматически, ручных
  действий с куками/кэшем больше не требуется.

---

## 2026-05-30 (ночь-6) — Scene-фото обложки (photo prompt v2) + версионирование промпта в pipeline

- **Запрос Лёши (по скрину iPhone):** абстрактный процедурный арт «плохо выглядит, сложно
  ассоциировать». Нужно: РЕАЛЬНОЕ фото того, что происходит (сцена мнемоники), в ОДНОМ стиле для
  всей полки; сохранить текущий промпт как «версию 1» для отката; зашить логику в pipeline, чтобы
  будущие батчи генерили обложку тем же стилем. После теста уточнил: палитра жизнерадостная (зелень,
  голубое небо), а не тёмная — первый вариант был «восхождение на Марсе в апокалипсис».
- **Backend `cover.py`:** реестр `PROMPT_VERSIONS` {1: `_build_prompt_v1` (старая абстракция,
  сохранена ДОСЛОВНО), 2: `_build_prompt_v2` (фото)}. Активная версия — `active_prompt_version()`
  из `Settings.cover_prompt_version` (default 2, env `ENGLISH_COVER_PROMPT_VERSION`). `build_prompt`
  диспатчит по версии и принимает `subtitle` (= сцена мнемоники). `generate_cover(... subtitle,
  version)` пишет файл по версии `<slug>.v<N>.png` → откат к v1 = бесплатный кэш-свап. v2-промпт:
  единый кинематографичный editorial-photo, жизнерадостный дневной свет (синее небо/зелёная трава
  для outdoor), человек со спины/без лица, без текста, 1:1 (привязка к тёмному espresso снята).
- **Pipeline (как title/subtitle):** `content.upsert(auto_cover=None→settings, force_cover)` +
  `_maybe_generate_cover` (fill-once: пропуск если `cover_path` есть и не force; ошибки глотаются —
  фейл генерации не ломает запись, фронт падает на процедурный арт). `config.auto_cover=True`.
  `load_path`/`upsert_authored`/`seed` наследуют (синхронно). Paste-`/imports/commit` остаётся в
  фоне (`_gen_cover_bg` теперь получает `subtitle`), чтобы не блокировать HTTP. CLI
  `app/gencovers.py` (`--all | <id>... | --version N | --force`).
- **Frontend:** `ui/Art.tsx::BatchCover` — `<img cover_url>` с `onError`-fallback на `BatchArt`
  (процедурный арт). Вписан в Library (hero+грид), BatchDetail, мини-плеер (App.tsx). CSS
  `.bcover{object-fit:cover}`. `BatchArt` остаётся как fallback. tsc+vite build зелёные.
- **Тест-петля (по согласованию с Лёшей):** генерил #1 локально (venv + master `.env`, без эха
  ключей), открывал PNG в Preview (инлайн-картинки в чате у Лёши не отрисовывались → `open` файла).
  v1 тёмный → правка промта → v2 жизнерадостный, утверждён. ~$0.34 локально (2× тест #1).
- **Деплой:** rsync → пересобран ТОЛЬКО `english_app` (caddy/чужие не тронуты). На проде корректные
  subtitle (#1 Восхождение на гору, #2 Раскопки, #3 Выступление на сцене) → `gencovers --all
  --force` (~$0.50) → все 3 в зелёно-голубом дневном свете, `cover_path` → `*.v2.png`. Гейт
  подтверждён: `/api`→401, `/audio`→401, `/covers/*`→303, `/`→303, `/login`→200. Картинки вынесены
  `docker cp`+`scp` на локаль, открыты в Preview — стиль когерентный. ⚠️ Айфону нужен reload (новый
  бандл + cover_url сменился на `.v2.png`); по HTTP/IP SW не кэширует → подхватит сразу.

---

## 2026-05-30 (вечер) — Образ-подписи мнемоник (LLM в пайплайне) + счётчик фраз на карточках

- **Запрос Лёши (по скрину iPhone):** подпись под заголовком должна быть очень короткой (1–3 слова,
  можно одно) summary — что за мнемо-текст / ассоциация (образ: сцена, гора, поле), а не пересказ
  первой фразы истории («ни о чём не говорит»). И должна быть цифра — сколько фраз в блоке. Логика
  как у заголовков — встроить в стандартный pipeline.
- **Backend:** `titling.suggest_subtitle(mnemo)` — образ мнемоники в 1–3 слова. Читает ТОЛЬКО текст
  мнемоники: theme намеренно НЕ передаётся (метафора темы расходится с образом истории — «лестница»
  темы над «горой» мнемоники → openai с theme выдавал «Лестница», без theme «Восхождение на гору»).
  Промпт `_SUBTITLE_SYSTEM`: «назови сам образ — сцена/место/метафора; 1–3 слова; не пересказывай».
  Переиспользует `_clean` (sentence-case). `content.upsert(auto_subtitle, force_subtitle)` +
  `_resolve_subtitle` (тот же lifecycle, что у title: человеческий > prior > LLM). Прокинуто во все
  3 пути создания: `load_path`, `/imports/commit`, `/imports/upsert` (`auto_subtitle=True`). CLI
  `app/resubtitle.py` (бэкфилл, зеркало `retitle`). `batches.py _preview` БОЛЬШЕ не режет 1-ю фразу
  истории → теперь `subtitle → theme` (убрал мёртвый mnemo-запрос в list). batch1 JSON `subtitle` → "".
- **Frontend:** `.album-meta` (`{phrase_count} patterns`) на карточках грида — у hero уже был
  `.feature-meta`. `.album-sub` нижний отступ ужат под meta. Подпись теперь короткая → 2-line clamp
  фактически не нужен, но безвреден.
- **Проверка (Claude_Preview 375×812):** hero + грид показывают короткую подпись-образ + `N PATTERNS`.
  ⚠️ Поймал stale-кэш: на localhost (secure context) SW регистрируется и отдавал старый бандл
  (обложки прошлых сессий) → снял `navigator.serviceWorker.unregister()` + `caches.delete()` + reload.
  На проде (HTTP/IP) SW не регистрируется → у пользователя обновится сразу.
- **Деплой:** сначала dry-run на хосте (curl к Meridian напрямую, без записи — Лёша попросил
  превью). Подтвердил → build → rsync → пересобран ТОЛЬКО `english_app` (caddy/чужие контейнеры не
  тронуты) → `docker exec english_app python -m app.resubtitle --all` (через Meridian). На проде:
  #1 «Восхождение на гору» (11 фраз), #2 «Раскопки» (9), #3 «Выступление на сцене» (8). Заголовок =
  функция, подпись = образ — дублей нет. Гейт подтверждён: `/api`→401, `/audio`→401, `/`→303,
  `/login`→200. ✅

---

## 2026-05-30 (день) — Essence-названия батчей (LLM в пайплайне) + фикс синих заголовков

- **Запрос Лёши (по скрину iPhone):** название коллекции должно отражать СУТЬ батча (что за фразы,
  что они позволяют делать в разговоре), а не мнемоническую метафору («Восхождение», «Раскопки»,
  «Сцена» — это имена мнемо-историй). LLM должна читать фразы и присваивать essence-название.
  Встроить в стандартный pipeline создания батчей.
- **Backend:** новый `app/titling.py` — `suggest_title(phrases, theme)` через `llm.chat`
  (temperature=0.4), системный промпт «назови функциональную суть, не метафору; 2–4 слова; русский
  sentence-case». `_sentence_case()` чинит английский Title Case слабых моделей (gpt-4o-mini выдавал
  «Запрос Мнений» → «Запрос мнений»), сохраняя аббревиатуры (KPI). `llm.chat` получил параметр
  `temperature`. `content.upsert(auto_title, force_title)` + `_resolve_title`: человеческий title
  главнее, пустой → LLM генерит один раз и держит стабильно на re-seed, force → перегенерить.
  `load_path`/`commit`/`upsert_authored` передают `auto_title=True`. CLI `app/retitle.py`
  (`--all`/`<id>`/`--dry-run`) для существующих батчей. `BatchAuthor.title` теперь Optional;
  batch1 JSON title → "" (pipeline сам присвоит, re-seed не вернёт мнемо-имя).
- **Frontend fix:** `.album-title` не имел `color` → на iOS `<button>` рендерил системный СИНИЙ
  (в Chrome был чёрный, локально не поймал). Добавлен `color: var(--text)`. У `.feature-title`
  цвет был задан явно — потому hero был чёрный, а грид синий.
- **Деплой:** build → rsync → пересобран ТОЛЬКО `english_app` → `docker exec ... python -m
  app.retitle --all` (Meridian/claude-sonnet). Результат на проде:
  - #1 «Восхождение — лестница несогласия» → **«Несогласие с нарастающей прямотой»**
  - #2 «Раскопки» → **«Запрос мнения собеседника»**
  - #3 «Сцена» → **«Побуждение к откровенности»**
  Гейт цел: `/api`→401, `/`→303, `/login`→200. ✅ Новые батчи теперь авто-получают essence-название
  при импорте/seed через Meridian.
- **Открыто:** subtitle батчей 2/3 всё ещё деривится из 1-й фразы (не куратор); essence-генерация
  subtitle — возможный следующий шаг.

## 2026-05-30 (ночь-5) — Title-hero pivot + content-pipeline + деплой

- **Два запроса Лёши:** (1) построить понятный pipeline загрузок/корректировок и достроить БД,
  чтобы не хардкодить батчи руками (боль прошлой сессии — `/tmp/replace_batch1.py`); (2) дизайн-
  pivot: «заголовок батча — герой, арт — поддерживающий; убрать синий полностью; random keyword-
  цепочки → осмысленные мнемо-превью; единый абстрактный арт вместо индивидуальных AI-картинок».
  Частично разворачивает прошлый AI-cover-вектор.
- **Backend pipeline:** `content.py` — авторский слой `BatchAuthor`/`PhraseAuthor`, `to_batch_in`
  деривит order_index (1-based) / intensity (round((i-1)/(n-1),3)) / zone order / spans (через
  `importer._compute_spans`); `upsert` = create-or-replace by slug (обновляет поля, `deleted_at=None`,
  wipe+rewrite детей, сохраняет Batch.id + cover); `to_authoring` — round-trip export. Эндпоинты:
  `POST /imports/upsert`, `POST /imports/seed`, `GET /batches/{id}/export`. CLI `python -m app.seed`
  грузит `backend/content/*.json` (DetachedInstanceError-фикс: поля захватываются внутри сессии).
- **БД:** колонка `batch.subtitle` (db.py `_migrate` additive ALTER), `BatchIn.subtitle` в schemas,
  `auto_cover=False` в config. `batches.py` list отдаёт `subtitle` + `_preview()` (subtitle → 1-я
  фраза story_ru → theme); добавлен `import re` (был NameError-краш). Батч 1 (лестница несогласия,
  11 фраз, zones Curious/Cautious/Direct) накатан из `content/01-disagreement-ladder.json`.
- **Frontend:** `ui/Art.tsx` — процедурный `BatchArt` (FNV-1a hash + mulberry32 PRNG по slug,
  тёплая палитра, SVG-блобы+grain, без сети/стоимости); `lib/accent.ts` → единый `INK`.
  Library/BatchDetail/App.tsx переписаны на title-hero + тонкую арт-полосу; `ui/Cover.tsx` удалён.
  CSS: `--accent:#26211B`, `--mark:#9A7B4F`; де-blue `.seq-more`/`.anchor`; `.bart/.feature/.album/
  .detail-art`. `api.ts` типы +`subtitle`/`preview`. `tsc --noEmit` clean.
- **Проверка (Claude_Preview 375×812):** Library (заголовок-герой, арт-полоса, превью «От „помоги
  понять"…»), BatchDetail (большой заголовок, мнемо-цепочка 11 якорей, «Mnemonic» в `--mark`),
  Mnemonic (все 11 якорей подсвечены — spans OK), Playback (плеер играет 0:40, герой-якорь). Синего
  нет нигде. Консоль чистая. ✅
- **Деплой:** `npm run build` локально → rsync → пересобран ТОЛЬКО `english_app` (caddy Up 10h, не
  тронут) → `docker exec english_app python -m app.seed` → батч 1 updated in place (id=1, slug `batch`,
  subtitle set, 11 фраз, mnemo len 258). Гейт post-deploy: `/api/batches`→401, `/audio/*`→401,
  `/`→303, `/login`→200, ассеты→303 (тоже под гейтом). ✅
- **Открыто:** батчи 2/3 (`batch-2/3`) без кураторского subtitle (превью из 1-й фразы) — можно дать
  через export→edit→`/upsert`; мелкий CSS-nit Mnemonic about-таблицы (`ThemeЛестница…` без пробела).

## 2026-05-29 (ночь-4) — AI-обложки батчей (album-cover identity) + деплой

- **Дизайн-ревью Лёши:** приложение чистое, но «обезличенное» — карточки = цветной
  прямоугольник + заголовок, без обложки product можно спутать с finance/meditation/habit-
  трекером. Директива: каждому батчу — уникальная абстрактная премиум AI-обложка (визуальная
  метафора, как Apple Music album cover / Apple Books), доминантный hero, убрать EXEC-коды,
  вынести мнемонику-цепочку на карточку. Движок выбран Лёшей: **AI-картинки** (не процедурный SVG).
- **Backend:** `cover.py` — метафоры по ключевым словам темы + editorial-промпт; OpenAI Images
  (gpt-image-1, 1024², quality=high). Миграция `cover_path` (`db.py _migrate` — additive ALTER,
  т.к. SQLModel create_all не меняет существующие таблицы). `/covers` StaticFiles-mount **за**
  cookie-гейтом. POST `/api/batches/{id}/cover` (metaphor/quality/force). Авто-генерация фоном
  при импорте (`config.auto_cover=True`, `BackgroundTasks`). list/detail отдают `cover_url`.
- **Frontend:** `ui/Cover.tsx` (`BatchCover` — gradient-фон + fade-in img, onError→fallback на
  градиент, генерация-фейл не фатальна). Library переписан: доминантный `.feature` hero (aspect
  4/5, картинка во весь экран, мнемоника+title+play-FAB поверх scrim), `.album` грид (обложка +
  title + `.achain` цепочка). BatchDetail `.detail-art` (3/2). Mini-player cover. EXEC-коды
  (`execCode`) удалены. `vite.config.ts` — прокси `/covers` для dev + preview.
- **⚠️ Промпт-урок:** v1 «light, airy, minimal, generous negative space» → вымытая пастель
  (Headspace-стайл, не читается как обложка). v2 «rich, deep, immersive, dramatic focal point,
  bold volumetric light, dark moody gradient, high contrast» + метафоры переписаны с
  «quiet/gentle/soft» на «powerful/intense/dramatic» → насыщенные album-covers. Force-regen.
- **3 обложки:** Восхождение (золотой восход света-лестницы), Раскопки (тёмные пласты, раскол
  с раскалённым оранжевым ядром), Сцена (театральный сноп света сквозь тьму). Серия цельная,
  но каждая узнаваема. Проверено в браузере (Claude_Preview 375×812): hero + грид + BatchDetail. ✅
- **Деплой:** `npm run build` локально → rsync (искл. data/.env/venv) → `docker compose -p
  english -f docker-compose.deploy.yml up -d --build english_app` (пересобран **только** app;
  caddy Up 5h, не тронут). Прод-обложки сгенерены через `docker exec english_app python -c
  "...cover.generate_cover(force=True)..."` (минуя HTTP-гейт; OPENAI_API_KEY уже в env контейнера),
  3 PNG в volume `english_english_data` (~1.6–1.8 MB каждый, ~$0.50 за три).
- **Пост-деплой verify:** без cookie `/api`→401, `/`→303→`/login`, `/login`→200, `/covers/*`→303.
  Authenticated smoke (пароль из `/root/english/.env`, не печатался): `/api/batches`→200 (все 3
  возвращают `cover_url`), `/covers/{batch,batch-2,batch-3}.png`→200 image/png. Гейт цел. ✅

## 2026-05-29 (ночь-3) — Фиксы плеера: Shuffle/Loop + одно проигрывание (с iPhone)

- **С айфона Лёши пришли 4 бага плеера** (Playback-экран) — все исправлены и задеплоены:
  1. **Shuffle не работал** — «сбрасывал экран и ничего не происходило». Причина:
     `reshuffle` всегда форсил `full_random` (не toggle), рвал сессию (`setSession(null)`
     → экран в 0:00) и не возобновлял playback. Фикс (`PlayerContext.tsx`): reshuffle стал
     toggle (`full_random ↔ ordered`), и сохраняет playback через ре-рендер
     (`wasPlaying = !audio.paused` → передаётся как `autoplay` в `prepare`).
  2. **Shuffle включён по умолчанию** — initial `order = "full_random"`, `playBatch`
     дефолт `order ?? "full_random"`, Library hero play → `full_random`.
  3. **Loop включён по умолчанию** — initial `loop = true` (нативный `a.loop`,
     зацикливает весь session-WAV; toggle проверен: on→off→on меняет `audio.loop`).
  4. **Фраза звучала дважды** — `listening_repeats` дефолт был 1 (phrase + 1 repeat).
     Фикс: модель `Setting.listening_repeats` 1→0, `default_order_mode` ordered→full_random;
     живой Setting-row (id=1) обновлён через `PUT /api/settings` на local + host (модельный
     дефолт не трогает существующий row — поэтому PUT обязателен).
- **Проверено в браузере** (Claude_Preview, mobile 375×812, dev Vite :5173): Shuffle+Loop
  on by default; Shuffle-toggle переключает shuffled↔ordered, список переупорядочивается,
  **playback не прерывается** (t прогрессирует); Loop-toggle меняет `audio.loop`; listening
  играет каждую фразу один раз (Сцена 34.7с/8 фраз, Восхождение 16.7с/5).
- **Редеплой на Hetzner** (изолированно): rsync `frontend/dist` (--delete) + `backend/app`
  → `docker compose -p english up -d --build english_app` (caddy не трогали, Up 4h).
  Пост-деплой verify: settings `listening_repeats=0`/`full_random`, listening-рендер batch1
  = 5 фраз×1, shuffled, dur 16.7с; gate `/`→303, `/api`→401, login title ок. ✅
  ⚠️ На айфоне нужно перезагрузить страницу/PWA (сменились хеши dist-ассетов).

## 2026-05-29 (ночь-2) — Импорт 2 реальных батчей «Раскопки» + «Сцена» (local + prod)

- **Разблокирован импорт** (ждал paste Лёши): он прислал полный лог Claude.ai с двумя
  новыми батчами. Оба собраны в формат детерминированного парсера и залиты **и в local,
  и в продакшен-БД на Hetzner** через import-API приложения (`/api/imports/parse` →
  `commit`), с авторизацией через cookie-gate (login POST → cookie jar, токен после
  заливки удалён с хоста).
- **«Раскопки»** (probing/вопросы, копаешь вниз) — 9 фраз, 3 зоны
  **Curious (1-3) / Probing (4-6) / Pressing (7-9)**, мнемо «копаешь поле» (READ→THINKING→
  TAKE→LAND→SHOES→GUT→MISSING→TRUE→STAND). Якорь = главное слово фразы (zero-зазор).
  Parser deterministic, **9/9 спанов**, ноль warnings. На хосте id=2 (slug batch-2).
- **«Сцена»** (charisma/вытянуть мнение без вопросов, по шкале харизмы) — 8 фраз, 3 зоны.
  Якоря: Echo→Pause→Label→Guess→Lean→Dumb→Devil→Elephant, мнемо «выходишь на сцену»
  (ECHO→PAUSE→LABEL→GUESS→LEAN→DUMB→DEVIL→ELEPHANT). **8/8 спанов**, ноль warnings.
  На хосте id=3 (slug batch-3).
  - **2 решения, отмечены для Лёши** (не выдумывал memorization-фразы): (1) **Pause** —
    английской фразы нет по смыслу (это молчание), поставлена ремарка-заглушка
    `(stay silent)`; (2) **зонам** даны короткие EN-имена под шкалу харизмы Лёши
    **Mechanical (1-2) / Warm (3-5) / Presence (6-8)** (он сам описал 1-2 «техника без
    личности», 3-5 «внимание/тепло», 6-8 «присутствие»). Echo использует его же пример
    `…undervalued?`.
- **Три батча = система** (по словам Лёши): Раскопки (pull вопросом, вниз) + Сцена
  (pull присутствием) + Восхождение (push позицией, вверх). Хост теперь: Восхождение(5),
  Раскопки(9), Сцена(8).
- **Аудио НЕ прогревалось** (cost-bearing OpenAI TTS) — рендерится при первом Play.
  Прогрев кэша — по отдельному go-ahead.

## 2026-05-29 (ночь) — Премиум-редизайн «English Executive» + редеплой

- **Полный ребрендинг UI «Executive English» → «English Executive»** под Product Vision
  (Apple Music / Audible / Headspace). НЕ language-learning, без геймификации
  (badges/XP/streaks/progress bars убраны как класс).
- **Дизайн-система** (`index.css` переписан): светлые токены bg #F8F8F6 / card #FFF /
  border #ECECEC / text #111 / muted #6B6B6B; 5 accent-палитр (Soft Indigo, Warm Sand,
  Sage, Muted Coral, Dusty Blue), accent назначается батчу детерминированно по `id % 5`;
  SF Pro Display/Text; доминантные anchor-глаголы; spring-переходы.
- **6 экранов** (новые файлы в `src/pages/`): Library (hero Current Focus + 2-col album
  grid), Batch Detail (мнемо-цепочка + phrase cards), **Phrase Playback** (Apple-Music-
  lyrics: гигантский anchor-hero + scrub + transport + Speed/Shuffle/Loop/Favorite +
  pattern-list с plan-driven подсветкой текущей фразы), Mnemonic (anchor-чипы + story),
  Profile, Settings/Import (рестайл).
- **Глобальный плеер** (`src/player/PlayerContext.tsx`): один персистентный `<audio>`,
  воспроизведение переживает смену роутов (Apple-Music-style); мини-плеер + нижняя
  навигация Library/Playback/Profile. Helpers: `src/lib/accent.ts`, `src/ui/icons.tsx`.
  Удалены старые `BatchPage/BatchList/Player/MnemoView` (логика мигрировала).
- **🐛 Bug fix:** мини-плеер уезжал за правый край (left=187.5, width=359 на 375vw) —
  keyframe `fade-up` анимировал `transform` и затирал центрирующий `translateX(-50%)`
  (с `both` финальный `transform:none` оставался). Введён keyframe `mini-rise`
  (`translate(-50%, …)`). `index.css:60`.
- **Login-страница** (`backend/app/main.py`) ребрендирована + переведена с тёмной на
  светлую премиум-тему (#F8F8F6, indigo CTA, SF Pro, rounded). FastAPI title тоже обновлён.
- **Проверено в браузере** (Claude_Preview MCP, mobile 375×812): все 6 экранов; golden
  path Library → Batch Detail → Play All → Playback с **реальной TTS-сессией** —
  gapless-аудио играет (t прогрессирует, dur 34.45с), lyrics-подсветка корректно следует
  за плеем (Understand → Read по мере воспроизведения). `npm run build` зелёный
  (tsc + vite, CSS 14.38kB, JS 234.91kB).
- **Редеплой на Hetzner** (изолированно, без влияния на другие контейнеры):
  rsync `frontend/dist` + `backend/app` → `docker compose -p english -f
  docker-compose.deploy.yml up -d --build english_app` (только app, `english_caddy`
  не трогали). Секреты на хосте подтверждены (ENGLISH_APP_PASSWORD len 11 →
  cookie gate активен, COOKIE_SECRET 64, OPENAI_API_KEY 164). Пост-деплой verify:
  `/` → 303 /login, `/api/health` + `/api/batches` → 401, login title
  «English Executive — вход». ✅

## 2026-05-29 (вечер) — Деплой на Hetzner по IP + фикс TTS-WAV бага

- **Проверена мобильная вёрстка** (playwright, viewport 390×844): все экраны
  (Батчи/Плеер/Мнема/Фразы/Импорт/Настройки) рендерятся чисто. Поправлены 2 мелочи
  в `index.html`: добавлен `mobile-web-app-capable` (старый `apple-…` deprecated) +
  `<link rel=icon>` (404 favicon).
- **Задеплоено на Hetzner по IP:** http://89.167.122.76:8090 за Caddy basic-auth
  (alexey/<pw>). Контейнеры `english_app` + `english_caddy`, project `-p english`,
  код в `/root/english`, volume `english_english_data`. Фронт собран локально,
  на хост едет готовый `dist` (Dockerfile.deploy без node — экономия RAM/диска).
  Детали доступа/редеплоя — `accessAndSafety.md`.
- **🐛 Найден и исправлен P0-баг рендера аудио** (его не ловил smoke со стабом TTS):
  OpenAI `tts-1` отдаёт **streaming-WAV с placeholder-размерами** (`RIFF ffffffff …
  data ffffffff`) → `wave.getnframes()` = 2147483647 → `setparams()` копировал битый
  nframes → `36 + nframes*2` переполнял uint32 в заголовке (`'L' format requires
  0 <= number <= 4294967295`), `/api/sessions` падал в 502.
  Фикс: `audio.py` задаёт channels/sampwidth/framerate по отдельности (wave сам
  считает nframes по факту записи); `tts.py:_wav_duration` меряет длительность по
  фактическим PCM-байтам. PCM-данные были корректны изначально.
- **Проверено на живом хосте с реальным OpenAI:** recall (55.85с, 2.68 МБ) и
  listening (33.35с, 1.60 МБ) — 200, валидный RIFF, аудио с HTTP Range (206).
  Кэш фраз прогрет → первый тап с телефона мгновенный, без повторной траты.

## 2026-05-29 — Challenge → ТЗ v1 → MVP v0.1 реализован

### Challenge & ТЗ
- Прогнан `/challenge` (Claude Opus 4.8 ∥ ChatGPT Extended), сведён в синтез,
  архив в `_inbox/challenge-2026-05-29-0035.md`.
- ТЗ переписан v0→v1: active recall как дефолт-режим, server-rendered gapless audio
  (iOS-таймеры в фоне умирают), offline-first (SW + Cache API), JSON-as-truth +
  LLM как one-time importer с approval gate, provider abstraction, span-based мнема.

### Backend (FastAPI + SQLModel + SQLite WAL)
- 9 таблиц: Batch/Zone/Phrase/MnemoStory/ContextExample/AudioAsset/PlaybackSession/
  ReviewEvent/Setting; WAL + busy_timeout + FK pragma.
- Import pipeline: детерминированный парсер (regex по нумерации/зонам/раскладу) +
  LLM-фолбэк через provider abstraction (Meridian→Anthropic→OpenAI auto-resolve);
  spans мнемы по позициям anchor'ов (не regex).
- TTS: дисковый кэш (sha256 key с normalization_version), OpenAI `tts-1`.
- Gapless-аудио: чистый Python `wave` (zero deps; ffmpeg нет локально) — синтез всех
  сегментов → сборка с silence-фреймами → один WAV + per-segment таймкоды.
- REST: imports(parse/commit), batches(list/get/delete/reviews), sessions(render),
  settings. SRS-lite (new/shaky/familiar/automatic).

### Frontend (React 18 + Vite + TS, PWA)
- BatchList / ImportBatch (paste→parse→editable preview→commit) / BatchPage
  (Плеер/Мнема/Фразы) / Player (recall+listening, order modes, single `<audio>`,
  таймкод-хайлайт, Media Session, offline download, SRS marks) / MnemoView
  (spans→tap-reveal, self-check blur) / Settings.
- Service Worker (shell + cache-first audio + network-first nav), manifest, PNG-иконки
  (сгенерены чистым Python zlib).

### Deploy scaffolding (НЕ задеплоено)
- Dockerfile (multi-stage node→python3.12-slim+ffmpeg), docker-compose, Caddyfile
  (basic_auth). Hetzner deploy — отдельный approval-gated шаг.

### Проверки
- Backend smoke (TTS застаблен): parse/spans/commit/get/render(39s,25 seg)/SRS — PASS.
- `npm run build` — PASS (39 modules, 223KB JS).
- Живой HTTP: health/parse/SPA-at-root/manifest/icon — все 200.

### Открытые (требуют пользователя / устройства)
- Реальный TTS-прогон (стоит копейки) — нужен go-ahead на трату.
- iOS background-audio на реальном айфоне (P0-риск, локально не проверяемо).
- Hetzner deploy — требует approval (shared prod host).

## 2026-05-11 — Initial Memory Bank seed
- Создана структура `.claude/` для проекта
- Заполнен projectbrief, architecture, techContext, accessAndSafety из существующей памяти
- TODO: enrich из Notion (когда подключим)
