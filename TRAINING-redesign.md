# Training / Practice — редизайн в swipe-deck

> Дизайн-спека раздела «Практика» как Tinder-style колоды карточек.
> Версия 1 · автор: Claude (по ТЗ Алексея) · 2026-06-06
> Привязка к коду: ссылки на реальные файлы/поля даны inline. Сверять с `DESIGN.md`.

---

## 0. TL;DR — ключевые решения

1. **Никакой новой сущности «trigger phrase».** Карточка строится на существующей `Phrase`
   (`models.py:38`): фронт = `gloss_ru` (RU-ситуация-стимул, «триггер»), целевой ответ = `phrase_en`,
   `anchor` = опциональный хинт, `batch.title`/`section` = контекст.
2. **Два режима в одном разделе** через сегмент-переключатель сверху: **Swipe Practice** (само-оценка
   свайпом) и **Answer Check** (голос → AI-скоринг → flip → подтверждение).
3. **Answer Check переиспользует `POST /api/training/score-phrase`** почти как есть (STT + LLM + EWMA +
   `PhraseAttempt`). Добавляем только запись `TrainingEvent` для режима/сессии/feedback.
4. **Источник колоды — кросс-батчевый weighted deck.** Новый `GET /api/training/deck?batch_ids=...`.
   Клиент передаёт активные in-progress батчи (из localStorage `ee-progress-*`), сервер возвращает
   адаптивно взвешенную последовательность фраз с anti-repeat.
5. **Разделяем сигналы.** Спонтанная само-оценка свайпом НЕ пишется в `Phrase.avg_score` (это EWMA
   устного recall). Для свайпов — отдельный `self_ewma`, чтобы не загрязнять «правду» произношения.
6. **Свайп/flip строим нативно** (pointer events + CSS transform + Web Animations API), без новой
   зависимости — в проекте уже так сделана drag-навигация (`App.tsx` `.nav-capsule`).
7. **Визуально in-line:** те же токены `--map-green #1C8C63`, `--spring cubic-bezier(.22,1,.36,1)`,
   карточка `--r-lg 26px` / white / `--shadow-lg`, `RecFab` 92px для микрофона, плавающая навигация
   не трогается. Никакого «школьного quiz».

---

## 1. Привязка к существующей архитектуре (что переиспользуем)

| Нужно по ТЗ | Что уже есть | Файл |
|---|---|---|
| trigger phrases по батчам | `Phrase.gloss_ru` / `phrase_en` / `anchor` | `models.py:38` |
| только активированные in-progress батчи | localStorage `ee-progress-{id}` (`activated`, `l3_passed`) | `lib/progress.ts` |
| статистика по батчу/фразе | `Phrase.avg_score/attempts/last_score/last_seen_at` (EWMA α=.3) | `models.py:48-53`, `training.py:49` |
| per-batch rollup | `GET /api/training/mastery` | `routers/training.py` |
| weighted-подбор (внутри батча) | `GET /api/training/rotation/{id}` (вес `11 - avg_score`) | `routers/training.py` |
| голос → текст → балл | `POST /api/training/score-phrase` (gate→LLM, `PhraseAttempt`) | `routers/training.py`, `scoring.py` |
| микрофон | `useRecorder()` (MediaRecorder + MIME-sniff) + `RecFab` 92px | `audio/useRecorder.ts`, `ui/RecFab.tsx` |
| результат-экран | `.result-card` (96px badge + score, fade-up) | `index.css` |
| лимит расходов | дневной cap 400 скорингов → fallback self-grade | `routers/training.py` |

**Чего НЕТ и что добавляем:**
- кросс-батчевый адаптивный deck-эндпоинт;
- лог событий тренировки (свайпы + ответы) с `training_mode/swipe_direction/session_id` →
  таблица `TrainingEvent`;
- summary сессии → таблица `TrainingSession`;
- пара additive-колонок в `Phrase` (`last_failed_at`, `last_success_at`, `self_ewma`);
- свайп/flip UI-механика (нативно).

---

## 2. Информационная архитектура и навигация

Плавающая навигация (`App.tsx` `TABS`) НЕ меняется: **Библиотека · Обучение · Практика**.
Раздел живёт под существующей вкладкой **Практика** (`/practice`). Текущий `Practice.tsx`
(prompt + `RecFab` + лог) заменяется на новый swipe-deck экран.

```
/practice                       ← новый Training-хаб
   ├─ Mode select (segmented)   ← Swipe Practice | Answer Check
   ├─ Card deck (1 карта)       ← адаптивная колода
   └─ Session summary (sheet)   ← после ~N карт / по кнопке «Закончить»
```

Старый `Practice.tsx` сохраняем в git-истории; новый компонент — `pages/Training.tsx`
(+ под-компоненты `ui/SwipeDeck.tsx`, `ui/TrainingCard.tsx`, `ui/CardMic.tsx`).

---

## 3. UX flow (end-to-end)

1. Пользователь тапает **Практика**.
2. **Empty-state** (если нет активных in-progress батчей): спокойная карточка
   «Активируй батч в Библиотеке, чтобы начать тренировку» + CTA на `/`. (Логика как в текущем
   `Practice.tsx` empty-state.)
3. Иначе — экран Training: сверху **сегмент-переключатель режима**, под ним **колода** (видна
   1 карта + лёгкий «хвост» 1–2 карт позади для глубины).
4. Пользователь тренируется:
   - **Swipe Practice:** читает RU-триггер → свайп вправо (знаю) / влево (не знаю). Карта улетает,
     `TrainingEvent` пишется, следующая подбирается адаптивно.
   - **Answer Check:** читает RU-триггер → тап микрофона на карте → говорит → AI скорит → карта
     делает **flip** → на обороте % + короткий feedback + кнопки **Success / Not Success** → выбор →
     карта улетает → следующая.
5. После короткой сессии (порог: ~12 карт ИЛИ тап «Закончить» в хедере) — мягкий **session summary**
   (bottom-sheet): сколько прошёл, strongest/weakest батчи, что требует внимания, CTA «Ещё подход» /
   «В обучение».

Прерывание: уход с экрана = авто-сохранение сессии (события уже записаны поштучно; summary считается
по `session_id`). Идемпотентность как в остальном проекте.

---

## 4. Экран выбора режима (mode select)

Не отдельный экран, а **segmented control** в шапке колоды (минимум кликов, mobile-first):

- Контейнер: pill `--r 18px`, фон `rgba(255,255,255,.58)` + `backdrop-filter: blur(26px)` (тот же
  стеклянный язык, что и nav). Внутри 2 сегмента.
- Активный сегмент — **liquid-glass под-pill** (повторяем `.nav-pill::before`: градиент `.96→.66`,
  `blur(24px)`, верхний блик, хроматическая кайма), скользит пружинно (`--spring`, `translateX`).
- Подписи: **Swipe** · **Answer** (или «Свайп» · «Голос»). Активный текст `#2B2118` (680),
  неактивный `#8E8E93`.
- Смена режима **не сбрасывает колоду** — текущая карта остаётся, меняется только взаимодействие
  (в Answer появляется микрофон). Это даёт ощущение одного живого инструмента, а не двух модулей.

Под переключателем — тонкая строка контекста: «На повторение · N карт» и маленький прогресс-тик
сессии (без очков/стриков — anti-gamification по projectbrief).

---

## 5. Карточка: front / back состояния

Размер: почти на всю ширину shell (max 480px), высота ~ 62vh, `--r-lg 26px`, белая, `--shadow-lg`.
Под ней — 1–2 «теневые» карты (смещение 8px + scale .96 + opacity .6) для глубины колоды.

### Front (оба режима)
- **Верх:** маленький тег батча/секции — `.chip` в `--map-green-soft` с текстом
  `batch.title` (или `section`-лейбл). Слева — точка-индикатор приоритета (тускло-зелёная =
  maintenance, насыщенная = слабое место). Без цифр.
- **Центр:** **RU-триггер** = `gloss_ru`, крупно (Body 22–26px, до 3 строк, центрирование).
  Это «проверочная фраза»/ситуация.
- **Хинт (опц.):** `anchor` маленькой капсулой снизу, появляется по тапу «Подсказка» (как в
  Lesson2 «Подсказать фразу»). По умолчанию скрыт — карточка чистая.
- **Answer-режим:** по центру-низу — **mic-control** (`CardMic`, ~64px, вписан в карту, не FAB на
  весь экран): idle = зелёный mic-глиф; recording = красный stop + `rec-pulse`; busy = «…».
  Переиспользует стили `RecFab`, уменьшенный.
- **Swipe-режим:** микрофона нет; вместо него подсказки-affordance: слева бледный ✕ «Не знаю»,
  справа бледная ✓ «Знаю», подсвечиваются по мере драга (см. §6).

### Back (только Answer Check, после flip)
- **Correctness:** большой % (берём `score*10` из `score-phrase`), 52px (как `.verdict-pct`),
  цвет зелёный ≥80% / янтарь 50–79% / `--danger` <50%. Под ним короткий **визуальный индикатор**
  качества — 5 сегментов-«пипсов» (зелёные = round(score/2)), без школьного «правильно/неправильно».
- **AI feedback summary:** 1 строка (из LLM; сейчас `score-phrase` возвращает только балл — см. §10,
  добавляем `feedback`). Плюс эталон: `correct_phrase` (`phrase_en`) мелким, чтобы было видно «как надо».
- **Что услышали:** `transcript` совсем мелко/мутно (доверие к оценке, не разбор диктанта).
- **Контролы:** две кнопки **Success** (зелёная) / **Not Success** (нейтральная outline). Это
  `manual_success_status` — пользователь подтверждает/переопределяет AI (важно для доверия и для
  будущей адаптивности). Выбор → карта улетает (анимация ухода как свайп вправо/влево соответственно).

Тон обеих сторон: спокойный executive-trainer, премиум, без иконок-наград, без конфетти.

---

## 6. Механика колоды и свайпа (interaction model)

Строим **нативно** (как drag-навигация в `App.tsx`): `onPointerDown/Move/Up` + `setPointerCapture`,
`touch-action: none` на карте.

**Драг:**
- `dx = clientX - startX`. Карта: `transform: translateX(dx) rotate(dx * 0.04deg)`,
  `transition: none` во время драга.
- Прозрачность affordance: левый ✕ `opacity = clamp(-dx/120,0,1)`, правый ✓ `opacity = clamp(dx/120,0,1)`.
  Лёгкая тонировка фона карты к зелёному/нейтральному краю.

**Порог принятия:** `|dx| > 0.32 * cardWidth` ИЛИ `velocity > 0.6px/ms` на отпускании.
- **Принято:** «бросок» — WAAPI animate `translateX(±150%) rotate(±12deg)`, opacity→0, ~260ms
  `cubic-bezier(.22,1,.36,1)`. На `finish` — карта размонтируется, deck сдвигается, следующая
  поднимается (scale .96→1, 220ms spring).
- **Не принято:** возврат `translateX(0) rotate(0)`, spring 320ms (`.22,1,.36,1`).

**Кнопочный путь (доступность / Answer back):** свайп можно инициировать программно — кнопки
✓/✕ и Success/Not Success запускают тот же «бросок» в нужную сторону. Один код ухода карты.

**Flip (Answer Check):**
- Контейнер карты `transform-style: preserve-3d`, фронт/бэк — два слоя `backface-visibility: hidden`,
  бэк повёрнут `rotateY(180deg)`.
- По завершении скоринга: `transform: rotateY(180deg)`, 520ms `--spring`, с лёгким `scale(1.02)` в
  середине (как «переворот живой карты»). Это единственная новая для проекта анимация (3D-flip) —
  токены те же.
- Свайпать карту во время записи/скоринга нельзя (drag заблокирован, пока `busy`).

**Anti-repeat в UI:** одна и та же фраза не возвращается, пока в колоде есть несыгранные кандидаты
(гарантирует сервер, см. §7), плюс клиентский cooldown-буфер последних 5 `phrase_id`.

---

## 7. Адаптивный подбор карточек (deck logic)

**Источник:** только активные in-progress батчи. Клиент собирает их из localStorage
(`activated===true && l3_passed!==true`) → передаёт `batch_ids` (паттерн как `/api/practice/questions`).
Completed-strong батчи клиент тоже может опционально подмешать как `maintenance_ids` (низкий вес).

**Сервер: `GET /api/training/deck?batch_ids=1,2,3&maintenance_ids=7,9&limit=40&exclude=...`**
возвращает взвешенно-перемешанную последовательность фраз (расширяем существующий weighted-rotation
на кросс-батч).

### Формула приоритета (review_priority)
Для каждой фразы-кандидата:

```
# нормировки 0..1
phrase_conf   = (avg_score/10) * (1 - 1/(1+attempts))      # уверенность по устному recall
                                                            # attempts=0 → 0 (новое = низкая уверенность)
batch_avg     = mean(avg_score фраз батча)                  # из mastery
batch_weak    = 1 - batch_avg/10
phrase_weak   = 1 - phrase_conf
fail_boost    = 1.0 если last_failed_at в пределах 24–72ч, иначе 0.3   # «возвращать, но не сразу»
new_boost     = 0.6 если attempts==0 (exploration)
maintenance   = 0.12 если батч в maintenance_ids (completed-strong → редко)

weight = (0.45*phrase_weak + 0.30*batch_weak + 0.15*fail_boost + 0.10*new_boost) * maint_factor
# maint_factor = maintenance (0.12) для maintenance-батчей, иначе 1.0
```

**Anti-«сразу подряд»:** фразы с `last_seen_at < 90 сек назад` или входящие в `exclude` (клиентский
cooldown) исключаются из выборки этого запроса. Недавно проваленную возвращаем «чаще, но не сразу» —
через `fail_boost`, при этом cooldown не даёт ей выпасть следующей же картой.

**Сэмплинг:** weighted-random без возврата (как `rotation` уже делает `random()*weight`-перестановку),
а не строгая сортировка — иначе колода детерминирована и предсказуема. Возвращаем `limit` карт;
клиент подкачивает следующую порцию, когда остаётся <8.

**Итог приоритетов (соответствие ТЗ):**
- низкая статистика батча → чаще (`batch_weak`);
- низкая статистика фразы → чаще (`phrase_weak`);
- недавно провалена → возвращать чаще, но не сразу (`fail_boost` + cooldown);
- успешно закрытые батчи → реже (клиент их обычно не шлёт; если шлёт как maintenance — `maint_factor`);
- completed-strong → редко, как maintenance.

---

## 8. Данные и БД

Конвенции проекта (`db.py:26`): SQLModel `table=True`, int autoincrement, UTC `datetime.now(timezone.utc)`,
миграции — **additive** через `create_all()` + ручной `ALTER TABLE` в `_migrate()`. Alembic нет.
**Single-user → `user_id` не нужен** (если хочется задел на будущее — константа `user_id=1`, по умолчанию опускаем).

### Новая таблица: `TrainingEvent` (сырой лог, обе модели)
```python
class TrainingEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)            # uuid сессии (генерит клиент)
    batch_id: int = Field(foreign_key="batch.id", index=True)
    phrase_id: int = Field(foreign_key="phrase.id", index=True)
    training_mode: str                              # "swipe" | "answer"
    shown_at: datetime = Field(default_factory=_now)
    response_time_ms: Optional[int] = None
    swipe_direction: Optional[str] = None           # "left" | "right" | None (answer)
    transcript: str = ""                            # answer-режим
    ai_score: Optional[int] = None                  # 0..10 (answer)
    ai_feedback: str = ""                           # короткий summary (answer)
    manual_success: Optional[bool] = None           # Success/Not Success / self-swipe
    attempt_number: int = 1                         # n-я попытка по этой фразе
    created_at: datetime = Field(default_factory=_now)
```
ТЗ-поле `user_answer_audio_ref` — **намеренно не храним аудио** (как сейчас в `PhraseAttempt`:
только transcript+score). Если позже понадобится — `audio_ref: Optional[str]` additive.

### Новая таблица: `TrainingSession` (summary)
```python
class TrainingSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True, unique=True)
    started_at: datetime = Field(default_factory=_now)
    ended_at: Optional[datetime] = None
    mode: str = ""                  # доминирующий режим
    cards_total: int = 0
    cards_known: int = 0            # swipe-right / Success
    cards_unknown: int = 0
    avg_score: Optional[float] = None
```
(Можно не материализовать, а агрегировать из `TrainingEvent` по `session_id` — для MVP считаем на лету,
таблицу заводим, когда summary станет тяжёлой.)

### Additive-колонки в `Phrase` (агрегаты из ТЗ, которых нет)
```python
last_failed_at: Optional[datetime] = None
last_success_at: Optional[datetime] = None
self_ewma: Optional[float] = None     # EWMA само-оценки свайпом (0..1), ОТДЕЛЬНО от avg_score
```
**Почему отдельный `self_ewma`:** `avg_score` — это «правда» устного recall (EWMA баллов 0..10).
Свайп — субъективная само-оценка; смешивать нельзя, иначе слабые места размоются. `self_ewma`
влияет на `phrase_weak` мягким весом, `avg_score` остаётся чистым.

ТЗ-агрегаты `success_rate / last_seen / confidence / review_priority` — **вычисляемые**, не хранимые:
- `success_rate` по батчу/фразе — из `TrainingEvent`/`avg_score`;
- `last_seen` = `Phrase.last_seen_at`;
- `confidence` = `phrase_conf` (формула §7);
- `review_priority` = `weight` (формула §7) — считается в deck-эндпоинте.
(Денормализуем в колонки только если профилирование покажет, что считать на лету дорого — для
single-user/SQLite это не проблема.)

---

## 9. API surface (новое/изменённое)

| Method | Path | Назначение |
|---|---|---|
| GET | `/api/training/deck?batch_ids=&maintenance_ids=&limit=&exclude=` | кросс-батчевая адаптивная колода фраз (§7). Ответ: `[{phrase_id, batch_id, batch_title, section, gloss_ru, anchor, phrase_en?, priority, conf}]`. `phrase_en` отдаём только в Answer-режиме (на бэке для эталона) — или всегда, т.к. приложение single-user за гейтом. |
| POST | `/api/training/swipe` | запись свайпа: `{session_id, phrase_id, batch_id, swipe_direction, response_time_ms}` → пишет `TrainingEvent` + обновляет `self_ewma`, `last_seen_at`. НЕ трогает `avg_score`. |
| POST | `/api/training/answer` | Answer Check: оборачивает существующий scoring. Принимает `{session_id, phrase_id, audio, latency_ms}` → вызывает текущий `score-phrase`-пайплайн (gate→LLM, пишет `PhraseAttempt`+EWMA), затем пишет `TrainingEvent(mode="answer", ai_score, ai_feedback, transcript)`. Возвращает `{score, correct_phrase, transcript, feedback, via, avg_score, attempts}`. |
| POST | `/api/training/answer/confirm` | `{event_id, manual_success}` → проставляет `manual_success`, обновляет `last_failed_at`/`last_success_at`. (Можно слить в один вызов, если подтверждение приходит сразу.) |
| GET | `/api/training/session/{session_id}/summary` | агрегат для session-summary sheet (§3). |

**Расширение scoring:** добавить в LLM-промпт `scoring.py` возврат `feedback` (1 короткая фраза),
сейчас отдаётся только `{"score"}`. Бэк-компат: `feedback` опционально, gate-путь даёт пустую строку.

**Лимит расходов:** Answer Check уважает дневной cap 400; при превышении клиент скрывает микрофон и
оставляет только Swipe Practice + self-grade на обороте (graceful degrade).

---

## 10. Анимационная логика (сводка, всё на токенах проекта)

| Анимация | Техника | Тайминг |
|---|---|---|
| Drag карты | pointer events → `translateX rotate`, `transition:none` | live |
| Бросок (accept) | WAAPI → `translateX(±150%) rotate(±12deg)` opacity→0 | 260ms `--spring` |
| Возврат (reject) | CSS → `translateX(0) rotate(0)` | 320ms `--spring` |
| Подъём следующей | CSS → `scale(.96→1) translateY(8→0)` | 220ms `--spring` |
| Flip (answer) | `rotateY(180deg)` preserve-3d, scale 1.02 в середине | 520ms `--spring` |
| Mic recording | reuse `rec-pulse` | 1.5s infinite |
| Вход экрана | reuse `fade-up` | .42s `--spring` |
| Появление verdict | reuse `.result-card` fade-up | — |

Нет bounce/конфетти/наград. Reduced-motion: при `prefers-reduced-motion` бросок и flip заменяем на
crossfade 180ms.

---

## 11. User stories

- Как пользователь, я открываю Практику и сразу вижу карту со слабого места — без настройки.
- Как пользователь, я свайпаю «знаю/не знаю» одной рукой в метро (Swipe Practice), и это копит
  статистику, не требуя голоса.
- Как пользователь, в тихом месте я переключаюсь в Answer Check, проговариваю фразу, получаю % и
  одну строку фидбэка, подтверждаю Success/Not Success.
- Как пользователь, я вижу, что проваленные недавно фразы возвращаются — но не «душат» одной и той же.
- Как пользователь, закрытые сильные батчи всплывают редко (поддержка), а слабые — часто.
- Как пользователь, после короткой сессии я вижу спокойный итог: где силён, где слаб, что повторить.
- Как пользователь, я доверяю оценке: могу переопределить AI кнопкой Not Success/Success.

## 12. Edge cases

- **Нет активных батчей** → empty-state + CTA в Библиотеку.
- **Активный батч без attempts** → новые фразы получают `new_boost`, не пустая колода.
- **Лимит скоринга (400/день)** → Answer Check выключает mic, остаётся Swipe + self-grade.
- **Нет микрофона / отказ в доступе (iOS только по жесту)** → подсказка + предложить Swipe-режим.
- **STT вернул мусор / <2 токенов** → gate уже даёт score 0; на обороте мягкое «не расслышал, ещё раз».
- **Сеть отвалилась при answer** → fallback string-similarity (уже в `scoring.py`), помечаем `via=fallback`.
- **Колода кончилась** (мало фраз) → сервер зацикливает с увеличенным cooldown; UI «на сегодня всё,
  заходи позже» если кандидатов < N.
- **Свайп и flip одновременно** → drag заблокирован, пока `busy` (запись/скоринг).
- **Уход с экрана посреди карты** → события уже записаны поштучно, сессия закрывается по таймауту.
- **PWA stale shell на iPhone** → известный кейс проекта, 1 reload (cache-headers уже чинят, `main.py`).
- **Дубли-свайпы (двойной бросок)** → guard на `finish`-колбэке, один `TrainingEvent` на карту.

## 13. MVP scope (фазированно)

**MVP (фаза 1) — Swipe Practice + адаптивная колода:**
- `pages/Training.tsx` + `ui/SwipeDeck.tsx` + `ui/TrainingCard.tsx` (только фронт).
- `GET /api/training/deck` (кросс-батч weighted).
- `POST /api/training/swipe` + `TrainingEvent` + `self_ewma` колонка.
- Сегмент-переключатель (Answer задизейблен/«скоро»).
- Session summary — простой агрегат на лету.
- Это уже даёт ценность (сбор слабых мест) при минимуме риска (без аудио/скоринга в новом UI).

**Фаза 2 — Answer Check:**
- `CardMic` + flip + back-side, `POST /api/training/answer` (обёртка над scoring), `feedback` в LLM.
- Success/Not Success → `manual_success`, `last_failed_at`/`last_success_at`.

**Фаза 3 — полировка:**
- maintenance-подмешивание completed-strong, reduced-motion, summary-sheet с strongest/weakest,
  материализация `TrainingSession` если нужно.

**Anti-scope (по projectbrief):** без очков/стриков/наград, без мультиюзера, без не-executive контента.

## 14. Чек-лист визуальной интеграции (no conflict)

- [ ] Цвета только из `:root` (`--map-green`, `--text/-2`, `--muted`, `--card`, `--bg`).
- [ ] Радиусы из шкалы (`--r-sm/r/r-lg`), карта = `--r-lg 26px`.
- [ ] Тени `--shadow` / `--shadow-lg`, без новых.
- [ ] Все переходы на `--spring cubic-bezier(.22,1,.36,1)`.
- [ ] Стекло переключателя/тегов = язык `.nav-pill` (blur+gloss+хром-кайма), не плоская заливка.
- [ ] Микрофон = уменьшенный `RecFab` (тот же глиф/цвета/`rec-pulse`).
- [ ] Типографика: триггер — Body 22–26, %, теги — Caption uppercase .08em.
- [ ] Плавающая навигация и мини-плеер не трогаются; учесть `padding-bottom` под nav (как у др. экранов).
- [ ] Фон экрана — тот же `linear-gradient(180deg,#FCFCFC,#F4F7F4)`.
- [ ] Сверить итог с `frontend/public/design-system.html` / `DESIGN.md`.

## 15. Открытые вопросы для Алексея

1. **Что на фронте карты** — RU-ситуация (`gloss_ru`, моё дефолт-решение) или сам `anchor`, или
   EN-фраза «переведи обратно»? Это меняет направление recall.
2. **Свайп вправо/влево** в Swipe Practice — оставляем «знаю/не знаю» (само-оценка) или хотим
   «лёгко/трудно» (3-уровневый, ближе к SRS)?
3. **Активация батчей** оставляем в localStorage (MVP) или переносим на сервер (нужно для будущей
   адаптивной траектории и кросс-устройства)?
4. **Длина сессии** до summary — фикс ~12 карт, по времени, или бесконечно до «Закончить»?
5. **MVP-порядок** — стартуем со Swipe-only (фаза 1), как предложено, или сразу обе модели?
