# Аудит контента — консилиум по всем батчам

**Дата:** 2026-05-31 · **Состав:** Opus (оркестратор/1-й эксперт) + GPT-4o (2-й эксперт) + **Claude Opus 4.8 (независимый 3-й ревьюер)** · **Раундов критики:** 3 + синтез · **Итог:** единогласие.

Задача: прогнать каждый существующий батч через критиков; убедиться, что (1) набор фраз соответствует заявленному навыку, (2) батч оптимален, (3) **ни одна фраза/якорь не повторяется между батчами**.

---

## 1. Что нашли

**7 батчей** (6 в проде + новый «Торг»). Точных дублей-фраз нет, но **5 коллизий якорей** (якорь — это слово, по тапу на которое всплывает фраза; один якорь не может жить в двух батчах):

| Якорь | Батч A | Батч B | Решение |
|---|---|---|---|
| `read`  | Несогласие «different read» | Узнать мнение «What's your read» | B оставляет (идиома живее); A → `angle` |
| `land`  | Несогласие «land differently» | Узнать мнение «Where do you land» | A оставляет; B-фраза — **внутр. дубль** со «Where do you stand» (#9), вырезана → `seeing` |
| `walk`  | Несогласие «Walk me through» | Торг «rather walk» | Торг оставляет («walk away» незаменимо); Несогласие → `run` |
| `pause` | Несогласие «What gives me pause» | Тактичная эмпатия «(stay silent)» | Несогласие оставляет; ТЭ-«фраза» — **ремарка, не реплика**, удалена |
| `lean`  | Тактичная эмпатия «where I'm leaning» | Захват внимания «Lean in» | Захват оставляет (яркий якорь); ТЭ пересобрана без него |

**Структурные проблемы:**
- **Несогласие** — раздут до 11 фраз; «Outlier» дублирует «Land», «Why» дублирует «Straight».
- **Тактичная эмпатия** — всего 8 фраз, из них 2 (`Echo: «…undervalued?»`, `Pause: «(stay silent)»`) — это **техники, а не произносимые реплики**. Батч пересобран полностью.
- Остальные (Захват / Заострить / Прямая просьба / Торг) — чистые, правок по сути нет.

**После правок: 63 якоря, все уникальны, каждый батч ровно по 9 фраз.**

### 3-й круг — независимая верификация Opus 4.8

Прогнал финальный каталог «вхолодную» через отдельную модель **Claude Opus 4.8** (не GPT). Что он поймал поверх GPT-консенсуса:

- **B3 #5** «Help me understand what's really underneath that.» содержал слово `understand` — а это **якорь B1 #1**. Рекуррентная коллизия, которую GPT пропустил. → переписано на **«Help me see what's really going on underneath.»** (якорь `Underneath` сохранён, мнемо не меняется).
- **B1 #5** — лёгкая шлифовка регистра: «My one hesitation **here** is…».
- **B3 task-fit** — заявленная задача «тактическая эмпатия (Восс)» не покрывает фразы #4 (self-disclosure) и #7 (провокация/devil's advocate). Это уже не чистый Восс, а «эмпатия → присутствие».
  - **Решение (единогласно Opus 4.8 + GPT-4o + оркестратор):** не выкидывать #4/#7 (они и есть смысл зоны **Presence**), а **переименовать задачу** под реальную дугу. Свап убил бы намеренно выстроенную зону Presence.
- **B4/B5/B6** — Opus 4.8 проверил полные 9-фразовые наборы + мнемо построчно: **APPROVED, без правок** (зоны эскалируют, якоря — реальные content-words, мнемо вплетает все 9 по порядку).

---

## 2. Финальный каталог (по батчам)

Изменённые строки помечены `←`. B4–B7 без изменений — приведены свёрнуто.

### B1 · «Несогласие» · `live-tone` · образ: Восхождение на гору
**Задача:** выразить несогласие, по нарастающей: от любопытства к прямоте. *(11 → 9)*

| # | Зона | Якорь | Фраза | |
|---|---|---|---|---|
| 1 | Curious | Understand | Help me understand the thinking there. | |
| 2 | Curious | **Run** | Run me through how you got to that number. | ← было `Walk` |
| 3 | Curious | **Angle** | Can I offer a different angle? | ← было `Read` |
| 4 | Cautious | Far | I'm not sure I'd go that far. | |
| 5 | Cautious | Hesitation | My one hesitation here is… | ← шлифовка (Opus 4.8) |
| 6 | Cautious | Pause | What gives me pause is… | |
| 7 | Direct | Land | I hear you, but here's where I'd land differently… | |
| 8 | Direct | Push | Let me push back on that a little. | |
| 9 | Direct | Straight | Let me be straight with you — I don't think that works. | |

Вырезано: `Outlier` (дублирует Land), `Why` (дублирует Straight).
**Мнемо (новое):** Ты хочешь understand эту гору — и медленно run вверх по тропе, на ходу ищешь другой angle, другой ракурс склона. Видишь, как far ещё до вершины, и внутри вспыхивает hesitation. Делаешь pause, выбираешь, куда land ногу, и push себя выше. И с самого пика говоришь тем, кто внизу, straight — прямо, без обиняков.

### B2 · «Узнать мнение» · `live-tone` · образ: Раскопки
**Задача:** вытянуть чужое мнение, по нарастающей: от мягкого к прямому. *(9, один свап)*

| # | Зона | Якорь | Фраза | |
|---|---|---|---|---|
| 1 | Curious | Read | What's your read on this? | |
| 2 | Curious | Thinking | How are you thinking about this? | |
| 3 | Curious | Take | I'd love to get your take. | |
| 4 | Probing | **Seeing** | What are you seeing that I'm not? | ← было `Land` |
| 5 | Probing | Shoes | What would you do in my shoes? | |
| 6 | Probing | Gut | What's your gut telling you? | |
| 7 | Pressing | Missing | Be honest — what am I missing here? | |
| 8 | Pressing | True | What would have to be true for you to get behind this? | |
| 9 | Pressing | Stand | Where do you actually stand on this? | |

**Мнемо (новое):** Ты стоишь на поле и read землю — где копать. Начинаешь thinking, прикидываешь. Берёшь, take, лопату. Вглядываешься — seeing, что скрыто под дёрном. Копаешь так глубоко, что shoes скрываются в яме. Доходишь до gut земли, до самого нутра. Чувствуешь — чего-то missing. Пробиваешься к true дну, к скале. И там, наконец, stand на твёрдом.

### B3 · «Эмпатия → присутствие» · `live-tone` · образ: Выступление на сцене
**Задача:** раскрыть собеседника: от ярлыков-отражений (Восс) через искренность к смелому присутствию — назвать невысказанное. *(пересобрано: 8 → 9 реальных реплик; задача переименована по итогам 3-го круга — было «Тактичная эмпатия»)*

| # | Зона | Якорь | Фраза | |
|---|---|---|---|---|
| 1 | Mechanical | **Sounds** | It sounds like the timeline's the real worry. | ← ярлык |
| 2 | Mechanical | **Seems** | Seems like something here isn't sitting right. | ← было `Echo` (фрагмент) |
| 3 | Mechanical | **Sense** | My sense is you're not fully sold — am I off? | |
| 4 | Warm | **Head** | Here's where my head's at — tell me where I'm wrong. | ← было `Lean` |
| 5 | Warm | **Underneath** | Help me see what's really going on underneath. | ← было `(stay silent)`; переписано (убран `understand` — коллизия с B1) |
| 6 | Warm | **Agenda** | You probably think I've got my own agenda here. | ← accusation audit |
| 7 | Presence | **Kill** | Honestly, I'd kill the whole thing myself — talk me out of it. | ← devil's advocate |
| 8 | Presence | Elephant | Feels like there's an elephant in the room nobody's naming — what is it? | ← якорь `elephant` теперь буквально во фразе |
| 9 | Presence | **Obvious** | I'm probably missing something obvious — what is it? | ← было `Dumb` |

**Мнемо (новое):** Ты на сцене. Зал гудит — ты ловишь его sounds, его звучание. Тебе seems, что в воздухе напряжение. Доверяешь sense, чутью артиста. Киваешь: вот где моя head, где я сейчас. Заглядываешь underneath, под маски первого ряда. Признаёшь вслух свой agenda, свой расчёт — и зал выдыхает. Потом резко: «я бы это kill, убил номер» — провоцируешь. Тычешь в elephant, в то, о чём все молчат. И называешь самое obvious, очевидное, что никто не сказал вслух.

### B4 · «Захват внимания» · `pitch` — **без изменений**
Picture · Quick · Hook | Catch · Lean · Bet | Knife · One · Grab

### B5 · «Заострить проблему» · `pitch` — **без изменений**
Frame · Crack · Real | Bleed · Stake · Tax | Window · Tide · Clock

### B6 · «Прямая просьба» · `pitch` — **без изменений**
Bridge · Door · Fit | Ask · Yes · Room | Skin · Handshake · Seal

### B7 · «Торг» · `negotiation` — **новый, без изменений по итогу аудита**
Start · Table · Map | Move · Give · Meet | Line · Floor · Walk

---

## 3. Что нужно для внедрения

| Батч | Изменение | Требует |
|---|---|---|
| B1 Несогласие | 11→9, 2 якоря, новое мнемо | новый JSON + регенерация мнемо-аудио |
| B2 Узнать мнение | 1 свап, новое мнемо | **создать локальный JSON** (его не было) + аудио |
| B3 Эмпатия → присутствие | полная пересборка + переименование задачи, новое мнемо | **создать локальный JSON** + аудио |
| B4–B6 | — | — |
| B7 Торг | — (новый) | сид + аудио (при заливке) |

> ⚠️ B2 и B3 существовали только в прод-БД — локальных content-файлов не было. Их нужно создать, чтобы каталог стал воспроизводимым из кода.
> ⚠️ Любая правка фраз требует **регенерации мнемо-аудио** (платный TTS) и **редеплоя** в прод — отдельным апрувом.

---

## 4. Деплой — ВЫПОЛНЕНО (2026-05-31)

Залито в прод (`english_app` на Hetzner) хирургически, без даунтайма и без пересборки образа:
- Созданы локальные JSON: `01-disagreement-ladder.json` (обновлён 11→9), `06-opinion-dig.json` (B2), `07-empathy-presence.json` (B3), `05-negotiation-anchor.json` (B7). Засинканы в `/root/english/backend/content/` (воспроизводимо при будущей пересборке).
- **Точечный сид** только изменённых батчей (`batch`, `batch-2`, `batch-3`, `negotiation-1`) — pitch-1/2/3 **не трогали** (их прогресс сохранён). Обложки B1/B2/B3 сохранены; B7 пока на процедурной обложке (платный gpt-image-1 не запускал).
- Перед сидом вычищены устаревшие per-phrase телеметрии (1 строка) — иначе FK constraint. Пакетный экзамен (`SequenceAttempt`, по batch_id) сохранён.
- **Мнемо-аудио** (платный gpt-4o-mini-tts) перегенерировано для всех 4 + прогреты все фразовые клипы (9/9 каждый). Проверено через реальный API за cookie-гейтом: 7 батчей, mnemo-full отдаётся 200 audio/mpeg.
- DB-итог: **7 батчей × 9 фраз = 63 якоря, все уникальны.** B3 переименован в «Эмпатия → присутствие».

### Найдено при верификации и ИСПРАВЛЕНО (B4 «Захват внимания» / pitch-1)
- **Дефект:** якоря `Hook` и `Knife` НЕ присутствовали буквально в своих фразах («Here's the one-liner…», «Let me cut to it…») — нарушение правила «якорь = слово из фразы». Консилиум это пропустил (ревью шёл по парам анкер↔фраза абстрактно). Поймано механической проверкой `anchor.lower() in phrase.lower()`.
- **Фикс (якоря сохранены → мнемо B4 не трогали, регенерация мнемо-аудио не нужна):**
  - `Hook` → «**Here's the hook** — we make X feel like Y.»
  - `Knife` → «Here's where **the knife comes down** — what actually matters.»
- **Деплой (2026-05-31):** локальный `02-pitch-hook.json` обновлён → засинкан на хост + `docker cp` в контейнер → точечный ре-сид `pitch-1` (с пред-очисткой per-phrase телеметрии; batch id / обложка / история экзамена сохранены) → прогреты только 2 изменённых фразовых клипа (Hook, Knife) → верификация через реальный API за cookie-гейтом: оба клипа отдаются `200 audio/x-wav`, mnemo-full `200 audio/mpeg`.
- **Финальная проверка всех 7 батчей через прод-API:** 63 фразы, **63 уникальных якоря, каждый якорь буквально в своей фразе** — PASS.
