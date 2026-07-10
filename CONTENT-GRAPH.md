# CONTENT-GRAPH — карта ассетов и их связей

> **Зачем этот файл.** Единственная точка входа для любой правки контента.
> Здесь: какие сущности есть, сколько их, что из чего порождается, и какую
> цепочку команд гнать после какого изменения. **Не читай все фразы/батчи,
> чтобы это выяснить** — читай этот файл, а списки конкретных проблемных
> мест бери из `python -m app.doctor` (он печатает slug'и и номера слотов).
>
> Проверяет соблюдение цепочек **детерминированный тестер `app.doctor`**
> (0 LLM-токенов): после любой правки он обязан вернуть `CLEAN`, иначе он
> сам говорит, какой шаг цепочки пропущен. Раздел «Тестер» ниже.

Обновлено: 2026-07-07 · перепись снята с прода (Hetzner, `english_app`).

---

## 1. Перепись ассетов (прод, 2026-07-07)

| Сущность | Кол-во | Где живёт | Источник правды | Кто создаёт |
|---|---|---|---|---|
| Batch | 90 (все curated) | БД | `backend/content/*.json` (89 файлов) + `close-meeting` (авторский, только БД) | `app.seed` / `content.upsert` |
| Zone | 271 (~3/батч) | БД | `zones` в content-файле | upsert |
| Phrase | 811 (~9/батч) | БД | `phrases[]` в content-файле | upsert / `app.rephrase` |
| **CheckPhrase** (проверочные) | **3191** (~4/фразу, `kind=stimulus, lang=en`) | **ТОЛЬКО БД** — content-файла НЕТ | БД = источник; human-readable снапшот `_prod_check_phrases.md` (2026-06-06, устаревает) | Курировались LLM-ом разово; **автогенератора нет** |
| MnemoStory (история + spans) | 90 | БД | `mnemo` в content-файле; spans вычисляются | upsert / `app.restory` |
| **PhraseIntent** (ходы Live, пофразово, 2026-07-09 v2) | 1–3/фразу (2044 связи) | **ТОЛЬКО БД** | `backend/app/intents_curated.json` (курировано вручную, ключ `slug`+`order_index`); словарь фиксирован — **10 ключей**: warm/clarify/pushback/hold/buy_time/lead/ask/close/repair/support | `python -m app.intents` — идемпотентный ресид (`source=manual` руками — сидер их НЕ трогает). **Авторитетный сигнал для боя.** Фраза без строк → фолбэк на BatchIntent → универсально |
| **BatchIntent** (ходы Live, грубый фолбэк) | 1–4/curated батч | **ТОЛЬКО БД** | `intents_curated.json` (батч-уровень); для батчей вне карты — фолбэк `SECTION_INTENTS` в `app/intents.py`; те же 10 ключей | `python -m app.intents` (тот же сид). Используется, только когда у фразы нет своих PhraseIntent (напр. приватный импорт). Батч без строк = универсальный |
| **PhraseEmbedding** (семантический индекс Live, 2026-07-09) | 1/фразу | **ТОЛЬКО БД** (derived-кэш — можно дропнуть и пересобрать) | derived: вектор текста «phrase_en+anchor+gloss+situation/task+**approved cues**» (text-embedding-3-small, 512d, L2-норм float32) | `python -m app.embeddings` (идемпотентно: пере-эмбеддит только изменившиеся по text_hash/model/dim). Боевой подбор ранжирует кандидатов косинусом; без индекса — фолбэк на keyword |
| ContextExample | 0 | БД | — | **спящая таблица**, нигде не используется |
| situation_ru / task_ru | на каждой Phrase | колонки Phrase | derived (LLM) | `app.gen_context` |
| gloss_ru | колонка Phrase | БД (+опц. в файле) | куратор; файл пустой = «оставить БД» | rephrase / upsert |
| i18n (es/de/fr): title/subtitle/theme/gloss/story+spans | `*_i18n` dict-колонки | БД | derived (LLM) от RU-базы | `app.i18n_content --refill` |
| Обложки | `cover_path` | volume + БД | derived (image LLM) | `app.gencovers` |
| TTS-аудио | AudioAsset (0 строк — кэш) | volume + БД | derived, ключ = hash(text,voice,…) | **саморегенерация on demand** — инвалидация не нужна |
| UserPhraseStat (SRS) | 12 | БД | **прогресс юзера, валюта = `phrase_id`** | приложение |
| TrainingEvent / PhraseAttempt / ReviewEvent | 39 / 19 / 0 | БД | история юзера (стрик — из TrainingEvent!) | приложение |

Пользователей: 5. Личность фразы = слот `(batch, order_index)`; `phrase.id`
должен пережить любую текстовую правку — иначе SRS-прогресс осиротеет
(контракт F3, коммит 889edc4).

---

## 2. Граф: что из чего порождается

```
content/NN-*.json ──upsert/rephrase──▶ Batch / Zone / Phrase(anchor, en, gloss_ru)
        │                                   │
        │ mnemo ──restory──▶ MnemoStory.story_ru ──▶ spans (детерминир. пересчёт)
        │                                   │
        ▼                                   ▼
   Phrase.anchor+en+gloss ──gen_context──▶ situation_ru / task_ru   (LLM)
        │                ──(вручную/LLM)──▶ CheckPhrase cues        (нет автогена!)
        │                                   │
        ▼                                   ▼
   RU-база (title/subtitle/theme/gloss/story) ──i18n_content --refill──▶ *_i18n (LLM)
        │
        ▼
   phrase_en ──on demand──▶ AudioAsset (TTS)      title/theme ──gencovers──▶ cover

app/intents_curated.json ──app.intents──▶ PhraseIntent (пофразово, авторитет) + BatchIntent (фолбэк)
        (ключ slug+order_index)                        │ ход фразы = ось релевантности боевого режима

Phrase(en+anchor+gloss+situation/task) + CheckPhrase(approved) ──app.embeddings──▶ PhraseEmbedding
        │ вектор = «ситуации, которые закрывает фраза» — косинусный отбор кандидатов в Live
```

Прогресс (UserPhraseStat, TrainingEvent, PhraseAttempt, ReviewEvent) висит на
`phrase_id` СБОКУ от этого графа: контент можно перегенерировать целиком,
прогресс — нельзя. Всё, что мутит `phrase_id`, идёт только через
guard-ованный `content.upsert` (блок при живом прогрессе / явный force).

---

## 3. Матрица правок: что меняю → что гнать → что показать юзеру

Все команды — внутри контейнера: `docker exec -i english_app python -m <модуль>`.
После КАЖДОЙ цепочки — `python -m app.doctor` (обязан быть CLEAN).

| Меняю | Инвалидируется автоматически | Цепочка (по порядку) | Юзеру на проверку |
|---|---|---|---|
| **phrase_en / anchor** (текст фразы, слот тот же) | rephrase сам чистит: situation/task, gloss_i18n; **УДАЛЯЕТ cues этой фразы**; spans устаревают; **PhraseEmbedding устаревает по text_hash** (doctor красный до пере-эмбеддинга). ⚠️ **PhraseIntent НЕ инвалидируется** — теги сидятся по `(slug, order_index)`, а слот тот же, поэтому СТАРЫЙ ход прилипнет к новой фразе, если не переразметить | 1) правка в content/*.json → `app.rephrase` 2) `app.restory` 3) **re-author cues** (см. §4) 4) **re-author тегов хода**: обнови эту фразу в `app/intents_curated.json` → `app.intents` 5) `app.gen_context` 6) `app.i18n_content --refill` 7) `app.embeddings` | новые cues (обязательно), **новый ход/тег**, новые situation/task |
| **ход фразы (PhraseIntent)** | — (не влияет на другой контент) | правка записи фразы в `app/intents_curated.json` (ключ `slug`+`order_index`) → `python -m app.intents` (идемпотентный ресид; `source=manual` руками сидер не трогает) | какие ходы делает фраза (1–3 из 10 ключей) |
| **gloss_ru** | rephrase чистит situation/task + gloss_i18n; cues НЕ трогаются; embedding устаревает | `app.rephrase` → `app.gen_context` → `i18n --refill` → `app.embeddings` | новый gloss + situation/task |
| **cues (CheckPhrase)** добавил/поменял | embedding фразы устаревает (cues входят в её вектор) | вставка по §4 → `python -m app.embeddings` | таблица cues на утверждение (§4) |
| **модель эмбеддингов** (`ENGLISH_MODEL_EMBED`/`_EMBED_DIM`) | весь индекс устаревает (model/dim в строке) | env-свап + рестарт → `python -m app.embeddings` (пересоберёт всё) | — |
| **мнемо-история** | — | правка `mnemo` в файле → `app.restory` (сам дропнет устаревшие story_i18n) → `i18n --refill` | история + подсветка якорей |
| **title** батча | `app.settitle`/`app.retitle` сами чистят title_i18n | settitle/retitle → `i18n --refill` | заголовок |
| **subtitle** | `app.resubtitle` чистит subtitle_i18n | resubtitle → `i18n --refill` | сабтайтл |
| **структура** (добавить/убрать/переставить фразы, zones, theme) | ВСЁ детское пересоздаётся, phrase_id новые | `content.upsert` / `app.seed` — **блок при живом прогрессе** (409 / LiveProgressError); осознанно: `?force=true` / `--force-progress-loss` (сносит прогресс юзеров по батчу, включая историю стрика!) → затем ВСЯ цепочка: cues, gen_context, i18n, gencovers | предупредить юзера О ПОТЕРЕ прогресса ДО force |
| **обложки** | — | `app.gencovers` | картинка |
| **аудио/TTS** | ничего не делать | регенерируется само по hash текста | — |

⚠️ **Никогда**: не редактировать тексты через upsert (сносит phrase_id), не
писать в прод-SQLite через `sqlite3` CLI (foreign_keys=OFF → сироты; всё
через `docker exec … python`), не переставлять фразы «на месте» (rephrase
сам заблокирует reorder — прогресс перецепится на чужие фразы).

---

## 4. Проверочные фразы (CheckPhrase) — особый случай

- **3191 штук, только в БД, в git их НЕТ.** Бэкап = дамп БД (перед правками:
  `cp app.db app.db.bak-*`). `_prod_check_phrases.md` — снапшот для чтения.
- Это англоязычные **реплики-собеседника** (adjacency pair): cue задаёт
  ситуацию, ученик должен произнести целевую фразу. Training читает их
  первыми; при отсутствии — фолбэк на situation_ru.
- `app.rephrase` при смене текста фразы **удаляет её cues** (устаревший cue
  подводит к старой фразе, а скоринг сравнивает с новой → систематический
  фейл честных ответов).
- **Автогенератора нет** → регенерация вручную по протоколу:
  1. Взять из `app.doctor` список дыр (`CHECKPHRASE HOLES: slug #N,M`).
  2. Сгенерировать 3–5 cue на фразу LLM-ом **через ChatGPT/Chrome** (дев-работа
     — не платные API). Формат: короткая реплика собеседника на EN,
     НЕ содержащая слов целевой фразы, однозначно вызывающая её функцию.
  3. **Показать юзеру таблицей на утверждение** (фраза → варианты cues).
  4. После «ок» — вставить: `docker exec -i english_app python` +
     `models.CheckPhrase(phrase_id=…, batch_id=…, text=…, lang="en",
     kind="stimulus", order_index=…, status="approved")`.
  5. `python -m app.embeddings` — approved cues входят в вектор фразы
     (семантический индекс Live), без пере-эмбеддинга doctor красный.
  6. `app.doctor` → CLEAN.

---

## 5. Тестер: `python -m app.doctor [--fix]`

Детерминированный, без LLM, exit 1 при проблемах.

**Запускается сам — помнить о нём не нужно** (везде report-only; `--fix`
остаётся осознанным ручным действием):

1. **В приложении**: через ~2 мин после старта и далее раз в сутки → отчёт в
   `docker logs english_app` (строки `-- doctor (daily monitor)`).
2. **При каждой мутации каталога по HTTP**: ответы `/api/imports/upsert` и
   `/api/imports/seed` содержат ключ `"doctor"` со свежим отчётом — после
   replace это одновременно список оставшихся шагов регенерации.
3. **В конце каждого CLI-шага цепочки**: rephrase, restory, seed,
   seed_presence, gen_context, i18n_content сами печатают вердикт
   (`DOCTOR: CLEAN` / список проблем) перед выходом.

Проверки:

| # | Проверка | Ключ | Фикс |
|---|---|---|---|
| 1 | Сироты (stats/attempts/reviews/cues/examples на мёртвых phrase_id) | `orphaned_*` | `--fix` удаляет; TrainingEvent — только репорт (стрик!) |
| 2 | Cross-attach (rowid reuse: stat.batch ≠ phrase.batch) | `cross_attached_stats` | вручную |
| 3 | Дубли SRS-строк | `duplicate_stats` | `--fix` (оставляет прогрессивнейшую) |
| 4 | Spans ≠ свежий пересчёт / якорь отсутствует в истории | `stale_spans` / `missing_anchors` | `app.restory` / править контент |
| 5 | Дрейф файлов vs БД (тексты / кол-во фраз) | `content_drift` / `structural_drift` | `app.rephrase` / re-author |
| 6 | Дыры кэшей: situation/task; i18n-дыры по **юнион-языкам каталога** (ловит и обнулённые переводы после retitle) | `missing_situation_task` / `i18n_holes` | `gen_context` / `i18n --refill` |
| 7 | **Дыры cues**: фразы без cues в закьюированном батче (след rephrase) + целиком незакьюированные батчи | `checkphrase_holes` / `uncued_batches` | re-author по §4 |
| 8 | **Индекс эмбеддингов**: фразы без вектора / вектор не совпадает с текущими текстами+cues+моделью (молчит, пока индекс пуст) | `embedding_holes` / `stale_embeddings` | `python -m app.embeddings` |

Гарантия «нельзя забыть»: rephrase удалил cues → doctor красный (в логах,
в ответах API и в конце каждого шага цепочки), пока не re-author'ишь;
retitle обнулил перевод → doctor красный, пока refill не долил. Удаление
батча — только soft-delete (`deleted_at`), дети и прогресс сохраняются;
hard-delete детей есть только в удалении аккаунта (чистит private-импорты
целиком). Известный долг на проде: `uncued_batches=1` (`close-meeting` —
cues никогда не авторились).

---

## 6. Дисциплина токенов (для будущих сессий Claude)

1. Правка контента начинается с ЭТОГО файла + `app.doctor`, а не с чтения
   89 json.
2. Точечный доступ: фраза = `(slug, order_index)`; grep по якорю; читать
   один content-файл, не каталог.
3. Списки «что сломано» даёт doctor — не пересканировать вручную.
4. Всё регенерированное LLM-ом (cues, истории, situation/task) — юзеру на
   проверку ДО записи в прод-БД; переводы (--refill) — механика, ревью не
   нужны.
5. Дев-LLM — через ChatGPT/Chrome; платные API только для продовых вызовов
   самого приложения (Meridian).

## 7. Поддержка карты

Новая производная сущность (или новый генератор) ⇒ в том же коммите:
(а) строка в перепись §1 и ребро в граф §2, (б) строка в матрицу §3,
(в) проверка в `app.doctor` + тест в `backend/tests/test_doctor.py`
(правило `backend/`-тестов: `.claude/rules/testing.md`).

Связанные документы: контракт прогресса — memory `content-progress-contract`
(коммит 889edc4); тест-карта — `backend/tests/README.md`; аудит педагогики —
`TZ-learning-audit.md`.
