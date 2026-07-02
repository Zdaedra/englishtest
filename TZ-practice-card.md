I have everything I need. The code confirms all the panel's factual findings. Now writing the merged, buildable ТЗ.

---

# ТЗ — Редизайн карточки Practice (`Training.tsx`)

> **Статус панели.** Все факты сверены с кодом (`Training.tsx` 1–523, `index.css` 1532–1561, 3060–3176, 3660–3719). Где раунды спорили — решение принято и обосновано в §9. Это single-card редизайн, не переархитектура: переиспользуем счётчик, `tr-score`, lens-рецепт nav-pill, leave/flip-анимации.

---

## 1. Цель и принцип

Practice-карточка — самая просматриваемая поверхность приложения; это «как начинается каждый rep». Сегодня она перегружена: на лице фото + **два** текстовых лейбла (`tr-pill` + `tr-situ`), стимул, всегда-видимая подсказка-чип, и 12 точек прогресса. В AI-режиме карточка к тому же **переворачивается**, и микрофон живёт на обороте как сплошной 128px эмеральдовый диск — это Material FAB, не Liquid Glass.

**Принцип (одна строка):**
> На лице карточки соревнуется за первый взгляд ровно один текст — стимул. Всё остальное — это либо картинка (сцена), либо один тег (домен), либо один контрол. Никакого обучающего текста на карточке после первых ~8 повторов.

Три «остановки взгляда», зафиксированы: **фото** (периферия — «где я») → **стимул** (первая фиксация — «что мне сказали») → **контрол** (микрофон в AI / tap-to-flip в non-AI — «что я делаю»).

---

## 2. Анатомия карточки (лицо, сверху вниз)

Финальный bare-state лица в обоих режимах: **фото + pill + стимул**. Больше ничего.

| Элемент | Код сегодня | Вердикт | Спецификация |
|---|---|---|---|
| **Фото / сцена** `.tr-photo` + `.tr-photo-fade` | L435–437, css 3102–3108 | **KEEP** | Высота **36%** (НЕ растить до 38% — нижнюю треть теперь забирает mic/result-зона, стимулу нужно больше воздуха, не меньше). Fade без изменений (`.96`-непрозрачная карточка к низу — это и есть фон, на котором читается стекло микрофона). |
| **Section pill** `.tr-pill` («CHARISMA») | L438, css 3111–3118 | **KEEP, демоут** | Один контрол-чрома, заслуживший место — glanceable доменный якорь. Уменьшить: `font-size: 0.75rem` (было 0.8125), `font-weight: 640`. Позиция без изменений `top:28px left:28px`. Один uppercase-слово, тег, не заголовок. |
| **`.tr-situ`** («Working the room» + IconProfile) | L439, css 3120–3125, map `SITU` L49–57 | **CUT** | Единогласно (4/4). Второй текстовый лейбл на том же фото, дублирует pill + сцену. Удалить JSX-нод (L439), функцию `situLabel` (L57), map `SITU` (L49–56), импорт `IconProfile` если он больше нигде не используется. |
| **STIMULUS** `.tr-stim` | L442, css 3133–3137 | **KEEP — герой** | Сохранить существующий `clamp(32px, 7vw, 44px)`, weight 600, line-height 1.14, `letter-spacing -.02em`, left-aligned. (Отклонено: pedagogy 26–30px — слишком мелко для героя самой видимой поверхности.) Max ~3 строки; при переполнении масштабируется через clamp, **никогда не truncate** — учащийся обязан прочитать всю строку, на которую отвечает. |
| **«Что бы ты ответил?» / divider / tap-hand** | — | **уже нет в этой ветке** | Брифа описывает старую верстку. Этих нодов в коде нет. **Не добавлять обратно** как текстовую строку (см. §9-A). Императив «ответь» несёт сам контрол (микрофон под стимулом / tap-to-flip), а явный глагол — гейтед-подсказка первых reps. |
| **Foot-cue** `.tr-foot-cue` (`practice.tapToAnswer`) | L445, css 3151 | **KEEP механизм, ПОЧИНИТЬ** | Уже гейтед `!experienced`. Но: (1) копи mode-correct, (2) порог 20→8, (3) счётчик считать по answer-complete, не по tap, (4) позиция per-mode. Детали в §6. |
| **Progress dots** `.tr-dots` (12) | L446–450, css 3072–3077 | **MOVE OFF-card** | 3/4 за вынос. Это session-meta, не контент карточки; на лице конкурируют со стимулом и **в AI-режиме физически налезают на inline-result в нижней трети**. Перенести в `Head`/`.tr-head`-зону над `.tr-deck`. Сжать: `gap:7px`, dot `5px`. **Fallback** (если не успеть чисто в этот проход): ≤5px, один muted-bronze, прижат к самому низу safe-area, **никогда выше контрола** — но это компромисс, не цель. |
| **`.tr-foot`** контейнер | L444, css 3141 | **CUT с карточки** | Держал только cue + dots; оба уходят. Удаление `.tr-foot` — настоящее упрощение, не просто перенос. |

После этого `face === "front"` рендерит: `.tr-photo` (img + fade + pill) и `.tr-body` (стимул). Контрол (микрофон AI / невидимый flip-target non-AI) — отдельно, см. §3/§5.

---

## 3. AI-режим (без переворота)

Сегодня AI **переворачивается**: микрофон на обороте (L489), результат на обороте, стимул переприколот через `tr-back-prompt` (L458). **Убираем flip целиком.** Карточка не вертится; стимул не покидает экран от prompt до result. Это и есть условие, при котором no-flip педагогически безопасен (стимул виден в момент говорения).

Состояния (всё на лице, нижняя треть = control-зона):

**State 1 — Prompt (idle).**
Стимул приколот сверху. Внизу-по-центру — единственный контрол: **Liquid-Glass микрофон** (§4). Карточка-тело **инертно** (нет flip): когда `canVoice`, убрать `role="button"`, `tabIndex`, `aria-label`, `onClick→flipToBack`, `onKeyDown` с корневого `.tr-card` — интерактивен только микрофон. (Сейчас эти хендлеры всегда на `.tr-card`, L420–429.)

**State 2 — Recording** (`speech.listening || rec.recording`).
Микрофон → recording-state (эмеральдовый, breathing-ring, stop-glyph). Лейбл под микрофоном: `practice.micListening` / `practice.micRecording`. **Стимул не скрывается, модель НЕ раскрывается.**

**State 3 — Scoring** (`busy`).
Микрофон → spinner (`tr-mic-dots`), `opacity:.7`, inert. Лейбл `practice.micChecking`.

**State 4 — Result, inline (та же карточка, без flip).**
Микрофон **морфит наружу** (scale .9 + fade, 160ms), `tr-score` **crossfade-in** в той же нижней зоне. Стимул остаётся приколот сверху (он и есть pinned reference — `tr-back-prompt` в AI не нужен).
Переиспользуем `tr-score` (L467–475) по стилю, но **порядок DOM переупорядочить** (педагогический must-fix, см. §9-G):

1. **% match** — `verdict-pct` + `pctClass`, как есть.
2. **Твой ответ (transcript)** — `result.transcript`, лейбл `practice.yourAnswer` («Ты сказал»). **Выше correct_phrase.** Сейчас transcript рендерится последним (L474) — поднять над L471.
3. **Правильный ответ** — `result.correct_phrase`, лейбл `practice.modelLabel` («Как сказал бы носитель»), эмеральдовый/distinct.
4. **Coach** — `coach.feedback` при `coachState === "done"`, последним.

(Опционально, рекомендовано, не блокер: 🔊 на `correct_phrase` через существующий `speakCue` — произношение.)

**Advance в AI — один «Дальше», НЕ judge-row** (§9-F).
% — это и есть вердикт. Деривируем `known = result.score >= 6` (как hands-free уже делает на L327), авто-вызываем `trainSwipe(... known?"right":"left" ...)` и `advance(known, dir)`, показываем одну glass-pill **«Дальше / Next»** (`practice.next`). Никакой пары «Угадал/Не угадал» в AI: ручной self-rating поверх объективного скора — лишний тап, который **загрязняет SRS-сигнал** (35% + «Угадал» = планировщик думает, что фраза знается).
*Визуально:* «Дальше» — **вторичный** контрол, pill-формы, материал `.tr-pill` (frosted), НЕ полный lens-рецепт. Lens зарезервирован за микрофоном (единственный hero-контрол).

---

## 4. Liquid-Glass кнопка микрофона

Заменяет `.tr-mic.big` (128px solid `--accent`, белая иконка — это FAB, не стекло). Новый класс `.tr-mic-glass`.

- **Размер/форма:** **76px** круг. (Спред панели 72/84/128 → 76: совпадает с существующим базовым `.tr-mic` токеном 76px css 3668 → один magic-number меньше; ≥44pt tap-target ×1.7; control-weight, не hero, не конкурирует со стимулом за фиксацию.)
- **Размещение:** **на карточке**, нижняя треть, absolute, bottom-center. `bottom: calc(56px + env(safe-area-inset-bottom))` (точки теперь off-card; clearance для floating-nav). `left:50%; transform:translateX(-50%)`. **На карточке, не под ней** (§9-C): стекло читается только когда рефрактит контент — над `.96`-непрозрачной нижней третью карточки оно живёт, над плоским `var(--card)` фоном страницы — умирает; плюс result рендерится там же, где был микрофон, морф в одной зоне.
- **Материал (idle) — взят дословно из nav-pill lens** (`index.css` 1532–1561), чтобы микрофон был провабельно тем же материалом; добавлены только эмеральдовый cast-shadow + эмеральдовая иконка для связи с `--accent`:

```css
.tr-mic-glass {
  position: absolute;
  bottom: calc(56px + env(safe-area-inset-bottom));
  left: 50%; transform: translateX(-50%);
  width: 76px; height: 76px; border-radius: 50%;
  border: 1px solid rgba(255,255,255,.7);
  display: grid; place-items: center;
  color: var(--accent);                              /* эмеральдовая иконка над стеклом — НИКОГДА white-on-fill */
  background: linear-gradient(180deg, rgba(255,255,255,.42) 0%, rgba(255,255,255,.16) 100%);
  -webkit-backdrop-filter: blur(24px) saturate(220%) brightness(1.08);
  backdrop-filter: blur(24px) saturate(220%) brightness(1.08);
  box-shadow:
    inset 0 2px 1px rgba(255,255,255,.95),           /* top gloss   — из nav lens */
    inset 0 -2px 2px rgba(0,0,0,.05),                /* bottom shade */
    inset 3px 0 2px rgba(120,190,255,.30),           /* cool rim L  — рефракция */
    inset -3px 0 2px rgba(255,150,205,.28),          /* warm rim R  — рефракция */
    0 12px 30px -10px rgba(28,140,99,.30),           /* emerald cast — связь с --accent */
    0 4px 12px rgba(17,17,17,.10);
  transition: transform .18s var(--spring), box-shadow .2s ease, opacity .16s ease;
}
.tr-mic-glass::after {                                /* specular cap — из nav-pill::after */
  content:""; position:absolute; top:5px; left:13px; right:13px; height:34%;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255,255,255,.9) 0%, rgba(255,255,255,0) 100%);
  pointer-events:none;
}
```
Иконка: `IconMic size={28}` в `--accent`.

- **States:**
  - **`:active` (press):** `transform: translateX(-50%) scale(.92)`; cool/warm rim падают до `.18` («сжатый гель»). Haptic `light` на press-down (`haptic` уже импортирован, L11).
  - **`.on` (recording):** стекло тинтуется эмеральдом (`+ rgba(28,140,99,.22)` overlay), **breathing ring** — псевдоэлемент `box-shadow: 0 0 0 0 rgba(28,140,99,.40) → 0 0 0 16px transparent`, 1.6s ease-in-out infinite. **НЕ** красный `rec-pulse` (css 3678 — старый язык). Stop-glyph переиспользует `.tr-mic-stop` (css 3696), но **тинт `--accent`, не `#fff`**. Haptic `medium` на record-start.
  - **`busy` (scoring):** `opacity:.7`, `.tr-mic-dots`, inert.
  - **Locked** (`canVoice===false`): стекло + `saturate(120%)`, иконка `--faint`, lock-бейдж `.tr-mic-badge` (css 3685), tap → `nav('/subscribe')`. Редкий кейс (locked = по определению non-AI; остаётся только для free-showcase-batch edge, где `ai_allowed` флипается per-card).
- **Idle = без лейбла.** Постоянный «Tap to speak» — это та самая повторяющаяся чрома, которую убираем. Лейбл только во время listening/recording/checking.
- **Motion (entrance):** при оседании новой карточки микрофон fade + rise 8px, 240ms `var(--spring)`, через ~80ms после посадки карточки — стимул читается первым, контрол вторым.
- **Морф в result:** fade+scale .9, 160ms → crossfade `tr-score` в ту же зону.
- **Haptics:** press `light`, record-start `medium`, result-shown `light`.

---

## 5. Non-AI режим (с переворотом)

Этот режим **сохраняется как есть по потоку** — flip остаётся, потому что объективного скора нет и self-rating легитимен.

- **Лицо:** идентично AI (фото + pill + стимул). Tap → `flip("back")` (keep `flipToBack`, L226). Карточка остаётся tap-target **только** в non-AI (`role="button"` и хендлеры рендерить условно по `!canVoice`).
- **Оборот** (`tr-back2`): приколотый стимул сверху `tr-back-prompt` (keep, L458–462) → модель `card.phrase_en` крупно (`tr-answer big`, L502), **с лейблом `practice.modelLabel` («Как сказал бы носитель»)** — читается как *модель*, не *ключ к ответу* → ряд **«Не угадал / Угадал»** (`tr-judge`, L505–510, keep).
- **Жест:** «Угадал» → swipe right, «Не угадал» → swipe left (`judge()` L235 → `advance` → `leaveCard`, без изменений).
- **Никакого микрофона** на этом обороте. (Сегодня non-AI и так показывает только `phrase_en`, L502 — добавляем только `modelLabel` над ним.)

Это единственный режим, где flip и self-rating выживают.

---

## 6. Подсказки и туториал

### 6.1 Lifecycle гейтед-подсказки (первые ~8 reps)

- **Порог 20 → 8.** Переименовать `EXPERIENCED_AT` → `HINT_REPS = 8` (L25). `experienced = getSwipes(uid) >= HINT_REPS` (L127, per-user persist уже есть). Обоснование числа — §9-B.
- **Считать по answer-complete, НЕ по tap** (критический баг-фикс, §9-D). Сейчас `countSwipe()` вызывается внутри `flipToBack` (L229) — то есть на flip, до любого ответа. В новом AI нет flip → счётчик **никогда не сработает → подсказка вечная**. Исправление: убрать bump из `flipToBack`; инкрементить:
  - **AI:** в `onMic`, на successful-score пути (когда `setResult(r)` отработал) — не на каждом нажатии.
  - **non-AI:** в `judge()` (swipe-away = завершённый rep).
- **Копи mode-correct** (single `practice.tapToAnswer` теперь дефект — в AI не «tap to answer», там жмут микрофон):
  - **AI:** `practice.hintTapMic` («Нажми и ответь голосом»), размещён **прямо над микрофоном**.
  - **non-AI:** `practice.hintTapFlip` («Коснись, чтобы ответить»), на месте старого foot.
- **Taper (низкая цена, adopt):** reps 1–6 `opacity:1`; reps 7–8 `opacity:.5`; rep 9+ не рендерится. Один `transition: opacity .3s ease`, без motion.
- **Build-rule (pedagogy concern):** подсказка — absolute-positioned overlay с **нулевым резервом layout**. Bare-карточка (фото+pill+стимул+контрол) верстается первой; подсказка — слой поверх, никогда layout-зависимость.
- Починить устаревший `aria-label={t("practice.tapToAnswer")}` (L422) — mode-correct.
- Никакой tap-hand-иконки на карточке. Никаких swipe-стрелок/направлений на лицах — ever.

### 6.2 Туториал (one-time)

**Решение: вынесен в отдельный тикет, не часть этого прохода** (§9-H). Полноэкранный многопанельный overlay — новая архитектура, нарушает «single-card redesign». В этот проход count-гейтед inline-подсказка (6.1) **и есть** вся онбординг-система.

Зафиксировать в тикете на будущее (для контекста, не строить сейчас):
- Триггер: один раз, при первом входе в Practice с реальной колодой (`card !== null`, `phase === "deck"`), гейт `ee-tutorial-seen-${uid}`. При смене режима free→AI — однопанельная mode-delta `ee-tutorial-ai-seen-${uid}` (только микрофон).
- Формат: full-screen Liquid-Glass overlay, ≤2 панели, dot-pager, всегда «Пропустить / Skip» + «Понятно / Got it».
- Учит per-mode: **AI** — «тебе говорят → жмёшь стекло-микрофон → говоришь → видишь скор тут же; карточка НЕ переворачивается» + «свайп = следующая». **non-AI** — «коснись → эталон» (единственное место для tap-hand-анимации) + «Угадал→вправо / Не угадал→влево».
- Re-access: «?» в Practice-хедере (единственная постоянная teaching-affordance — в чроме, не на карточке).

---

## 7. Что удаляем

JSX (`Training.tsx`):
- `.tr-situ` нод (L439) + `situLabel` (L57) + map `SITU` (L49–56) + импорт `IconProfile` (L14, если не используется больше).
- Flip в AI: для `canVoice` карточка не оборачивается; микрофон и result — на лице. `tr-back-prompt` в AI не рендерится.
- Judge-row «Угадал/Не угадал» в AI (заменён на «Дальше»).
- `role/tabIndex/aria-label/onClick/onKeyDown` с корневой `.tr-card` в AI-режиме.
- `.tr-foot` контейнер с лица (cue → over-mic, dots → header).

CSS (`index.css`):
- `.tr-situ` (3120–3125).
- `.tr-mic.big` (3675) — заменён на `.tr-mic-glass`.
- **Мёртвый код** (orphaned, нет JSX-ссылок — housekeeping раз уж в файле): `.tr-foot-row` / `.tr-sh` / `.tr-gesture` (3142–3150) и весь блок `.tr-reveal` (3154–3176).

i18n (все 4 локали — текст-чрома локализуется, English-контент остаётся English):
- старый единственный `practice.tapToAnswer` как card-cue — заменить на mode-correct (оставить ключ если используется в aria где-то ещё, но на карточке не использовать).

---

## 8. План реализации (`Training.tsx` + helpers)

**Шаг 1 — Константы/счётчик.**
- L25: `EXPERIENCED_AT = 20` → `HINT_REPS = 8`; обновить ссылки (L127, и убрать из `countSwipe` L222).
- Переписать инкремент: удалить `countSwipe()` из `flipToBack` (L229). Добавить bump в `onMic` после `setResult(r)` (оба пути: speech и recorder) и в `judge()`. Helper: `const completeRep = () => { if (bumpSwipes(uid) >= HINT_REPS) setExperienced(true); };`

**Шаг 2 — Срезать `tr-situ`.** Удалить L439, `situLabel` L57, `SITU` L49–56, импорт `IconProfile` если осиротел.

**Шаг 3 — Лицо (front).** Убрать `.tr-foot` (L444–451) с лица. Dots вынести в `Head`/над `.tr-deck`. Pill демоут (css). Подсказку сделать absolute-overlay, mode-correct, gated `!experienced`, с taper.

**Шаг 4 — AI no-flip.** Когда `canVoice && !handsFree`: рендерить микрофон (`.tr-mic-glass`) и (при `result`) `tr-score` **на лице** в нижней зоне, НЕ на обороте. Убрать flip-хендлеры с `.tr-card` для AI. Hands-free-ветка (L476–485, использует `flip("back")` в эффекте L309) **остаётся как есть** — это отдельный режим, не предмет редизайна; он по-прежнему может крутить карточку внутри своего лупа.
   - *Важно:* AI no-flip и hands-free flip сосуществуют. Условие микрофона-на-лице: `canVoice && !handsFree && !result` (idle) / `canVoice && !handsFree && result` (inline result). Hands-free продолжает свой `tr-back2`-путь.

**Шаг 5 — `tr-score` reorder.** Внутри блока (L467–475): поднять `result.transcript` (L474, обернуть в `practice.yourAnswer`-лейбл) **выше** `result.correct_phrase` (L471, обернуть в `practice.modelLabel`). Порядок: `verdict-pct` → transcript → correct_phrase → coach.

**Шаг 6 — Advance в AI.** После result: derive `known = result.score >= 6`; одна glass-pill «Дальше» → `api.trainSwipe(...)` + `advance(known, dir)`. Убрать judge-row для AI (оставить только non-AI).

**Шаг 7 — non-AI.** Над `card.phrase_en` (L502) добавить `practice.modelLabel`. Flow без изменений.

**Шаг 8 — Микрофон CSS.** Добавить `.tr-mic-glass` + `::after` + states (`:active`, `.on` + breathing-ring keyframes, `busy`, locked). Удалить `.tr-mic.big`. Удалить мёртвый CSS (§7).

**Шаг 9 — i18n.** Добавить во все 4 локали:

| ключ | ru | es | de | fr |
|---|---|---|---|---|
| `practice.next` | Дальше | Siguiente | Weiter | Suivant |
| `practice.modelLabel` | Как сказал бы носитель | Como diría un nativo | So sagt es ein Muttersprachler | Comme dirait un natif |
| `practice.yourAnswer` | Ты сказал | Has dicho | Du hast gesagt | Tu as dit |
| `practice.hintTapMic` | Нажми и ответь голосом | Pulsa y responde con voz | Tippen und per Stimme antworten | Touche et réponds à voix |
| `practice.hintTapFlip` | Коснись, чтобы ответить | Toca para responder | Zum Antworten tippen | Touche pour répondre |

### Верификация
- **iOS 26 sim (Capacitor / WKWebView):** layout bare-карточки (фото+pill+стимул, без foot/situ); AI no-flip (микрофон на лице, result inline, порядок %→transcript→correct→coach); «Дальше» advance; non-AI flip + judge + modelLabel; подсказка mode-correct, исчезает после 8 reps (проверить через `localStorage ee-swipes-*`); счётчик растёт по answer-complete, не по tap; мёртвый CSS не сломал верстку.
- **Только на реальном iPhone (sim ненадёжен):** Liquid-Glass рендер микрофона — `backdrop-filter` blur/saturate, cool/warm рим, specular cap, breathing-ring; haptics (light/medium); `env(safe-area-inset-bottom)` clearance под floating-nav; **aspect-ratio/width-trap** (см. memory `ios-safari-aspect-ratio-trap` — Safari мис-считает width при aspect-ratio+height; Chrome-preview это скроет).
- **Backend:** поведение не меняется (переиспользуются `trainAnswer`/`trainAnswerText`/`trainSwipe`/`coach`). Backend-тесты гонять не нужно (frontend-only), но если тронете что-то в `backend/` — `cd backend && python -m pytest` по правилу.

---

## 9. Решения по конфликтам панели (decided)

- **A. «Что бы ты ответил?» как строка — ОТКЛОНЕНО** (UX+glass+onboarding 3, pedagogy сама отозвала). Императив несут структурно: микрофон под стимулом = «ответь голосом», гейтед-подсказка = явный глагол первые 8 reps, остальное — туториал. Постоянная строка = ровно та повторяющаяся чрома, которую назвал фаундер. *Residual guard (post-launch, не сейчас):* если тесты покажут, что учащиеся читают стимул как comprehension-айтем — добавить крошечный quote-glyph/avatar на стимул, НЕ строку-инструкцию.
- **B. Порог = 8.** Спред 5/8/10/20. Свайп учится за 1–2 повтора, но есть два жеста (mic-press / flip) и путь смены режима. 5 — слишком туго для смены режима; 10 — подсказка живёт почти всю первую сессию (`SESSION_LEN=12`); **8** внутри фаундерского «~10» и уходит до конца первой сессии, не возвращается на второй.
- **C. Микрофон НА карточке** (glass+UX), не под ней (pedagogy overruled по интенту upheld). Стекло без контента под собой не рефрактит; result рендерится там же → морф в одной зоне; стимул-остаётся-видимым проще на одной поверхности.
- **D. Размер 76px.** 72 легковат для единственного контрола; 84 конкурирует со стимулом за фиксацию; 76 = существующий токен (один magic-number меньше).
- **E. Dots OFF-card** (3/4). Понижено с non-negotiable до strong-preference: glass-fallback (≤5px, прижат к низу, ниже контрола) приемлем как stopgap, не блокер шипа.
- **F. AI advance = один «Дальше»**, не judge-row (pedagogy, data-integrity). % — объективный вердикт; `known` деривируется из `score>=6` (как L327). Ручной self-rating загрязняет SRS. Self-rating живёт только в non-AI.
- **G. `tr-score` reorder — ОБЯЗАТЕЛЬНО.** «Reuse verbatim» сохраняет педагогический баг (модель видна раньше своего ответа). Reuse = стиль, не DOM-порядок. transcript над correct_phrase.
- **H. Туториал — отдельный тикет.** Full-screen overlay = новая архитектура, вне «single-card». В этот проход inline-подсказка = весь онбординг.

**Два самых высокорисковых тихих бага (не потерять):**
1. Инкремент счётчика **должен** уйти с `flipToBack` (L229) — иначе в AI (нет flip) подсказка вечная, в non-AI горит на мис-тапах.
2. `tr-score` reorder обязателен — иначе recognition-over-recall.

---

**Файлы:**
- `/Users/daedra/Documents/AI/Claude/english/frontend/src/pages/Training.tsx` — `HINT_REPS` L25; `countSwipe`/`flipToBack` L222/L229 (перенос инкремента); `SITU`/`situLabel` L49–57 + `tr-situ` JSX L439 (cut); AI-ветка L463–510 (no-flip, inline result, single «Дальше», derive known); `tr-score` reorder L467–475 (transcript L474 → над L471); карточные хендлеры L420–429 (условно по `!canVoice`); aria L422; dots relocate L446–450; modelLabel над L502.
- `/Users/daedra/Documents/AI/Claude/english/frontend/src/index.css` — lens-источник 1532–1561 (mirror); `.tr-mic.big` 3675 → `.tr-mic-glass`; `.tr-pill` демоут 3111–3118; `.tr-stim`/`.tr-body` 3129–3137; `.tr-dots` relocate 3072–3077; cut `.tr-situ` 3120–3125, `.tr-foot` 3141, dead `.tr-foot-row`/`.tr-sh`/`.tr-gesture` 3142–3150 + `.tr-reveal` 3154–3176; reuse `.tr-mic-stop` 3696, `.tr-mic-badge` 3685.
- `/Users/daedra/Documents/AI/Claude/english/frontend/src/i18n/locales/{ru,es,de,fr}.ts` — ключи `next`, `modelLabel`, `yourAnswer`, `hintTapMic`, `hintTapFlip`.