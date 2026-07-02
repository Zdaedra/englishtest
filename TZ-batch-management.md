# ТЗ — Сквозное управление бэчами через long-press (iOS context menu)

**Статус:** SPEC (реализацию не начинаем до подтверждения «открытых решений», §10).
**Дата:** 2026-06-21
**Автор запроса:** Лёша. Дословно: «сделай меню работы с бэчами **сильным нажатием** (long-press, как в айфоне)… добавлять в активные / удалять из активных… убирать из траектории обучения и добавлять в траекторию обучения… **сделай сквозным**… напиши сначала tz, проанализируй… добавь в туториал тоже это (пока копи)».

---

## 1. Цель

Единый, **сквозной** (один и тот же жест + меню на всех экранах, где есть бэч) способ управлять принадлежностью бэча к двум множествам:

- **Активные** (что в ротации колоды практики `/practice`).
- **Траектория обучения** (личный учебный путь — спайн на экране `Learning`).

Жест — **long-press / сильное нажатие** (iOS-style), открывает контекст-меню действий. Обычный тап остаётся прежним (переход в `/batch/{id}`).

Дополнительно: когда бэч **в активных**, в меню обязательна опция **«Убрать из активных»** (сейчас этого нет нигде в UI).

---

## 2. Текущая модель (как есть, с привязкой к коду)

### 2.1 «Активные» = выводимое множество `isEngaged`, а НЕ флаг
- Флаг активации: `BatchProgress.activated` + `activated_at` — [models.py:228](backend/app/models.py) (server), зеркалится в localStorage `ee-progress-{id}` — [progress.ts:23–50](frontend/src/lib/progress.ts).
- Предикат «вовлечён»: `isEngaged(p) = activated || l1_listened || l1_retold || l3_s1 || l3_s2 || l3_passed` — [progress.ts:19–21](frontend/src/lib/progress.ts).
- **Колода практики строится по `isEngaged`, не по `activated`**: `deckSources()` сканит все `ee-progress-*`, берёт `isEngaged`, делит на `active` (`!l3_passed`) и `maint` (`l3_passed`) — [Training.tsx:55–70](frontend/src/pages/Training.tsx). Далее `api.getDeck(active, {maintenanceIds: maint})`.
- ⚠️ **Критично:** значит «убрать из активных» нельзя сделать одним `activated:false` — если у бэча есть любой урок-флаг (`l1_listened` и т.п.), он остаётся `isEngaged` → остаётся в колоде. См. §3.2.

### 2.2 «Активировать» есть, «деактивировать» — нет
- Добавить в активные: кнопка «Активировать» в BatchHome → `setProgress(id, {activated:true})` → PUT `/api/progress/{id}`.
- Backend на активации: freemium-гейт + **лимит `max_active_batches`** (free) → HTTP 403; ставит `activated_at` — [progress.py:65–100](backend/app/routers/progress.py).
- **Убрать из активных: в UI невозможно сегодня.** `PUT /api/progress/{id}` технически примет `activated:false`, но бизнес-логики нет, и (см. 2.1) этого недостаточно для колоды.

### 2.3 «Траектория обучения» = выводимый путь, НЕ курируемое множество
- На экране `Learning` спайн строится из **всего каталога**: группировка по `section`, порядок секций = `prioritySectionSlugs(profile)`, внутри — по `created_at` — [Learning.tsx:167–187](frontend/src/pages/Learning.tsx).
- `flat` = плоская последовательность; `activeId` = первый не пройденный (`!l3_passed`) бэч — [Learning.tsx:189–199](frontend/src/pages/Learning.tsx).
- **Курирования нет:** каждый каталожный бэч уже «на траектории». Чтобы «убрать из траектории» / «добавить» — нужен новый признак принадлежности пути (см. §3.1).

### 2.4 Поверхности с бэч-карточками (что делать сквозным) — общего компонента НЕТ
| Экран | Где (file:line) | Класс | Тап сейчас |
|---|---|---|---|
| Library — активный ряд | [Library.tsx:352](frontend/src/pages/Library.tsx) | `.row-card` | `nav(/batch/{id})` |
| Library — карусели секций | [Library.tsx:385](frontend/src/pages/Library.tsx) | `.row-card` | `nav(/batch/{id})` |
| Library — поиск | [Library.tsx:219](frontend/src/pages/Library.tsx) | `.album` | `nav(/batch/{id})` |
| Library — focus hero | [Library.tsx:317](frontend/src/pages/Library.tsx) | hero | `nav(/batch/{id})` |
| Learning — sprint rail | [Learning.tsx:376](frontend/src/pages/Learning.tsx) | `.review-card` | `nav(/batch/{id})` |
| Learning — review rail | [Learning.tsx:405](frontend/src/pages/Learning.tsx) | `.review-card` | `nav(/batch/{id})` |
| Learning — узлы спайна (карта) | MapTrack SVG [Learning.tsx:23–131](frontend/src/pages/Learning.tsx) | SVG node | tap → бэч |

Все — `<button>`. **Long-press / contextmenu / action-sheet в проекте отсутствуют.** Есть только `haptic("light"|"medium"|"success"|"error")` — [session.ts:43](frontend/src/lib/session.ts), no-op в вебе, работает в нативе.

---

## 3. Модель данных — РЕШЕНИЕ (рекомендация)

Две оси. Рекомендуется **вложенность: активные ⊆ траектория** (нельзя дрилить то, чего нет на пути).

### 3.1 Ось «Траектория» → новый флаг `on_path`
- Новое поле `BatchProgress.on_path: bool = False` (+ `on_path_at`), зеркало в `BatchProgress` (ts) и localStorage.
- Экран `Learning` строит спайн **только из `on_path` бэчей** (вместо всего каталога). Library остаётся полным каталогом (там и «добавляют на путь»).
- **Миграция совместимости:** при бэкфилле `on_path = (activated OR любой урок-флаг)` — т.е. всё, что уже `isEngaged`, попадает на путь. Так текущие пользователи не теряют карту.
- Альтернатива (если не хотим новый столбец) — см. §10, Решение A.

### 3.2 Ось «Активные» → сделать `activated` единственным источником колоды
Проблема 2.1 решается так:
- `deckSources()` фильтрует по **`activated`**, а не по `isEngaged` — [Training.tsx:65](frontend/src/pages/Training.tsx) (`if (!p.activated) continue;`).
- Чтобы не сломать текущее поведение «начал урок → попал в практику»: **авто-активация** — там, где сейчас ставятся урок-флаги (`l1_listened` и т.д.), доставлять `activated:true`, если ещё не стоял. (Точки: BatchHome.activate уже ставит; добавить в местах простановки l1/l3.)
- Теперь «Убрать из активных» = `setProgress(id,{activated:false})` — детерминированно убирает из колоды. Урок-прогресс (`l1_*`,`l3_*`) сохраняется (не теряем историю); `on_path` не трогаем (бэч остаётся на пути, просто не в ротации).
- `isEngaged` остаётся для «In Progress» счётчика/бейджей (поведение бейджей не меняем).

### 3.3 Итоговая семантика
| Действие в меню | Эффект |
|---|---|
| Добавить в траекторию | `on_path:true` → появляется на карте Learning |
| Убрать из траектории | `on_path:false` (+ `activated:false`) → уходит с карты и из колоды |
| Добавить в активные | `activated:true` (+ авто `on_path:true`) → входит в колоду практики |
| Убрать из активных | `activated:false` → уходит из колоды; остаётся на карте |

---

## 4. Жест и меню (UX-спека)

### 4.1 Long-press механика (новый hook `useLongPress`)
- `onPointerDown` → старт таймера **500 мс**; запоминаем `x0,y0`.
- `onPointerMove` > **10px** в любую сторону → отмена (это скролл/драг).
- `onPointerUp` **до** 500 мс → отмена long-press → срабатывает обычный тап (навигация).
- Таймер сработал (палец ещё на месте) → `haptic("medium")` + открыть меню + **подавить** последующий click (флаг `suppressClickRef`, сбрасываемый на следующий tick), чтобы не было навигации после отпускания.
- `onPointerCancel`/`onContextMenu` (десктоп правый клик / iOS callout) → `preventDefault`, открыть меню. Также `style: { WebkitTouchCallout: "none", userSelect: "none" }` на карточке, чтобы iOS не показывал свой системный share-callout.
- `touch-action: pan-y` на карточках (как уже сделано для `.tr-card`), чтобы вертикальный скролл жил, а удержание ловилось.

### 4.2 Презентация меню — v1: bottom action-sheet
- Новый компонент `BatchActionSheet` (один на все экраны): затемнённый backdrop (tap = close) + нижний лист с Liquid-Glass верхом (переиспользовать рецепт линзы), заголовок = название бэча + обложка-миниатюра, ниже — список действий.
- Анимация: лист выезжает снизу (`translateY 100%→0`, spring), backdrop fade. Закрытие — обратно + по свайпу вниз.
- `haptic("medium")` на открытии, `haptic("success")` на успешном действии.
- **v2 (отдельным тикетом):** «настоящее» iOS-context-menu — поднятие карточки с blur фона и поповер. v1 листа достаточно по UX и надёжнее в WKWebView.

### 4.3 Содержимое меню — зависит от состояния бэча
Состояния: `completed` (`l3_passed`), `active` (`activated`), `on_path` (`on_path && !activated`), `off_path` (ни то ни другое), `locked` (freemium/план).

| Состояние | Пункты меню (сверху вниз) |
|---|---|
| off_path | **Добавить в траекторию** · Добавить в активные · Открыть бэч |
| on_path (не активен) | **Добавить в активные** · Убрать из траектории · Открыть бэч |
| active | **Убрать из активных** · Убрать из траектории · Открыть бэч |
| completed | Вернуть в активные (повтор) · Убрать из траектории · Открыть бэч |
| locked (freemium) | Действие показывается, но тап → переход `/subscribe` (см. §6) |

«Открыть бэч» дублирует обычный тап (на случай, если меню открыли случайно). Деструктивные («Убрать…») — красным (`--danger`).

---

## 5. Сквозная архитектура (DRY)

Чтобы «сделать сквозным» без копипасты по 7 поверхностям:

1. **`frontend/src/lib/useLongPress.ts`** — hook: `useLongPress(onLongPress, {onClick})` → возвращает props (`onPointerDown/Move/Up/Cancel`, `onClick`, `onContextMenu`, `style`). §4.1.
2. **`frontend/src/lib/batchActions.ts`** — чистая логика: `batchMenuState(id) → {state, items}` и исполнители `addToPath/removeFromPath/activate/deactivate(id)` поверх `setProgress` + freemium-проверки. Единый источник правды о пунктах меню.
3. **`frontend/src/ui/BatchActionSheet.tsx`** — презентация листа. Управляется через лёгкий контекст-провайдер `BatchMenuProvider` (в `App.tsx`), чтобы любой экран вызывал `openBatchMenu(batch)` без проп-дрилла.
4. **Подключение**: на каждой из 7 поверхностей (§2.4) к `<button>` добавить spread `useLongPress(() => openBatchMenu(b))`. Минимальное изменение на surface, вся логика — в общих модулях.
   - Для SVG-узлов карты (Learning MapTrack) — те же pointer-события на `<g>`/`<rect>` узла.

*Примечание:* выделять общий `<BatchCard>` целиком НЕ требуется (разная вёрстка `.row-card`/`.album`/`.review-card`/hero) — достаточно общего **поведения** (hook + sheet). Это дешевле и безопаснее, чем рефактор всей вёрстки.

---

## 6. Backend

- **Миграция:** добавить `on_path BOOL DEFAULT 0`, `on_path_at DATETIME NULL` в `BatchProgress` ([models.py:228](backend/app/models.py)); бэкфилл `on_path=1 WHERE activated OR l1_listened OR l1_retold OR l3_s1 OR l3_s2 OR l3_passed` (паттерн как DEFAULT-бэкфилл в [db.py](backend/app/db.py)).
- **PUT `/api/progress/{id}`** ([progress.py:65](backend/app/routers/progress.py)): принять `on_path` (+ ставить `on_path_at`); разрешить `activated:false` (деактивация — без гейта/лимита, всегда можно). Реактивация (`activated:true`) — **снова под лимитом `max_active_batches`** (free): вернуть 403 при превышении.
- **Сериализация** `ProgressRow` (+ `on_path`, `on_path_at`) — и `api.ts` тип `ProgressRow` (+ поля), `progress.ts` `BatchProgress` (+ `on_path`, `on_path_at`), `hydrateProgress` (+ маппинг), `setProgress` srv-вайтлист (+ `on_path`).
- **Тесты (правило `backend/tests/`):** это затрагивает **entitlements/лимиты и доступ** → обязателен тест:
  - деактивация всегда проходит (даже на free, даже сверх лимита);
  - реактивация сверх `max_active_batches` → 403;
  - `on_path` тогглится без лимита;
  - бэкфилл миграции ставит `on_path` существующим engaged-строкам.
  Файл: `backend/tests/test_progress.py` (или расширить существующий).

---

## 7. i18n (ключи, 4 локали ru/es/de/fr)
`batch.menu.addPath`, `batch.menu.removePath`, `batch.menu.addActive`, `batch.menu.removeActive`, `batch.menu.reactivate`, `batch.menu.open`, `batch.menu.title` (или используем имя бэча). RU-источник:
- addPath «Добавить в траекторию» · removePath «Убрать из траектории»
- addActive «Добавить в активные» · removeActive «Убрать из активных»
- reactivate «Повторить (в активные)» · open «Открыть бэч»

---

## 8. Edge cases
- **Freemium-лимит** на (ре)активации → 403: меню показывает пункт, исполнитель ловит 403 → тост + `nav("/subscribe")`. Деактивация/трасса — без лимита.
- **Долгое нажатие vs скролл/свайп** — порог 10px и 500мс; на свайп-колоде практики НЕ вешаем (там свайп = листание, отдельная семантика).
- **Десктоп/веб** — `onContextMenu` (правый клик) открывает то же меню; `haptic` no-op.
- **Случайное открытие** — backdrop-tap и «Открыть бэч» как escape.
- **Рассинхрон localStorage↔server** — оптимистично пишем локально (UI синхронен), PUT fire-and-forget как сейчас; при 403 откатываем локальное изменение.
- **Карта Learning при пустом `on_path`** — если пользователь убрал всё с пути: показать пустое состояние «Добавь бэчи из Библиотеки» (а не сломанный спайн).

---

## 9. Туториал (накопление, слой делаем СЛЕДУЮЩИМ тикетом)
Добавить пункт в [TZ-tutorial-backlog.md](TZ-tutorial-backlog.md): «Сильное нажатие на бэч → меню: в активные / на траекторию». Здесь только копим формулировку; оверлей-слой туториала — отдельная следующая задача (как договорились).

---

## 10. Решения (зафиксированы 2026-06-21)

- **A — модель «траектории»: ✅ A1 — ДВЕ ОСИ** (`on_path` + `activated`). Новый флаг `on_path` = курируемый путь; `Learning` рисует только его. activated ⊆ on_path. Миграция + бэкфилл (§3.1, §6).
- **B — источник колоды: ✅ ДА** — `deckSources()` переводим с `isEngaged` на `activated` + авто-активация при старте урока (§3.2). Нужно для надёжного «убрать из активных».
- **C — презентация:** v1 = bottom action-sheet (Liquid-Glass), iOS lift+blur — v2 (§4.2).
- **D — процесс: ✅ прогнать через `/consilium`** перед реализацией (ловим дыры модели до кода).

---

## 11. План реализации (после подтверждения §10)
1. Backend: миграция `on_path` + PUT-логика (деактивация/реактивация/трасса) + сериализация. Тест `test_progress.py`. `pytest`.
2. Плам­бинг типов: `api.ts` ProgressRow, `progress.ts` BatchProgress/hydrate/setProgress/`isOnPath`.
3. `deckSources()` → `activated`; авто-активация в точках урок-флагов.
4. `useLongPress.ts` + `batchActions.ts` + `BatchActionSheet.tsx` + `BatchMenuProvider` в App.tsx. CSS листа (Liquid-Glass).
5. Подключить жест на 7 поверхностях (§2.4), включая SVG-узлы карты.
6. `Learning` спайн: фильтр по `on_path` (+ пустое состояние).
7. i18n ×4. `tsc` → build → device.
8. Дописать пункт в `TZ-tutorial-backlog.md`.

---

## 12. Ревизия по итогам /consilium (2026-06-21)

Прогнали модель через консилиум (Claude Opus 4.8 High + GPT-5 High, Normal). **Сильный consensus**: модель «fundamentally sound», но **два пункта BROKEN у обеих моделей** + ряд risky. Вердикты (verdict·conf Claude/GPT):

| | Тема | Вердикт |
|---|---|---|
| C1 | Когерентность осей/переходов | risky 72 / 78 |
| **C2** | **Тихая потеря колоды при миграции** | **broken 88 / 92** |
| C3 | Maintenance-пул при миграции | risky 80 / 85 |
| C4 | Freemium-лимит | risky 78 / sound-w-risks 74 |
| **C5** | **Optimistic-write fire-and-forget** | **broken 82 / 88** |
| C6 | Long-press vs жесты | risky 72 / 82 |
| C7 | Полнота для сборки | broken 90 |

### Канонические состояния (закрепить)
```
isCompleted     = l3_passed
isInDeck        = activated
isActivePractice= activated && !l3_passed
isMaintenance   = activated && l3_passed
isOnPathOnly    = on_path && !activated
isOffPath       = !on_path && !activated
```
**Инвариант (клиент И сервер, сервер-authoritative):** `if (activated) on_path = true; if (!on_path) activated = false;`

### Action semantics (закрепить — устраняет orphan-состояния C1)
```
addToPath:      on_path=true (+on_path_at)
addToActive:    on_path=true, activated=true (+activated_at)
removeFromActive: activated=false
removeFromPath: on_path=false, activated=false   // также деактивирует
reactivate:     on_path=true, activated=true
```
### Menu — ВСЕГДА обе оси (ревизия 2026-06-21 по фидбеку Лёши)
Прошлый «ladder» показывал по одной оси за раз → для не-активных/не-на-траектории бэчей не было пунктов «Добавить». Исправлено: меню всегда = [ось активности] + [ось траектории] + «Открыть», по каждой оси add ИЛИ remove:
```
active  → "Убрать из активных"          | completed&!active → "Повторить" | else → "Добавить в активные"
on_path(=on_path||activated) → "Убрать из траектории"   | else → "Добавить в траекторию"
+ "Открыть"
```
Так: свежий бэч → [Добавить в активные · Добавить в траекторию · Открыть]; активный → [Убрать из активных · Убрать из траектории · Открыть]; на пути но не активен → [Добавить в активные · Убрать из траектории · Открыть]. «Добавить в активные» по инварианту ставит и on_path.

### P0 — блокеры (правят §3/§6, делать до фичи)
1. **Миграция (C2/C3, BROKEN).** НЕ оставлять `activated` как есть. Бэкфилл: **`activated = isEngaged`** И `on_path = isEngaged`. Иначе все, кто проходил уроки, но не жал «Активировать», **молча теряют колоду И review-пул** после перехода `deck = activated`. + grandfathering лимита для free (не выкидывать сверх-лимитные на миграции). + релиз-ноут «колода могла сократиться».
2. **Серверный инвариант** (не только локальный): сервер сам чистит `activated` при `on_path=false` и поднимает `on_path` при `activated=true`. Клиентский оптимизм ≠ источник правды.
3. **Versioned optimistic writes (C5, BROKEN).** Заменить fire-and-forget: awaited PUT + retry-queue; `client_mutation_id` + `base_updated_at`/per-field `updated_at` → LWW-reconcile при загрузке (мульти-девайс: один аккаунт, два устройства затирают друг друга); пересчёт deck/map после отката. Обрабатывать network/5xx/offline, не только 403.
4. **Menu priority + reactivate⇒on_path** (C1) — закрепить ладдер выше.
5. **Schema + PUT-контракт + migration script** для `on_path/on_path_at`.

### P1 — корректность / freemium
6. **Лимит считает только `activated && !l3_passed`** (maintenance и path — бесплатны). `on_path` НЕ лимитируем (path = планирование).
7. **Авто-активация при cap** (C4): не запирать уроки free-юзеру → либо уроки не требуют активации, либо flow «освободи слот» вместо отскока на `/subscribe`.
8. **iOS WebView жест** (C6): `-webkit-touch-callout:none; user-select:none`, `preventDefault` на `contextmenu`, `touchmove` с `passive:false`.
9. **Общий компонент/поведение до подключения** (уже в §5: hook+sheet) — не плодить жест ×7.
10. **Каталог = поверхность повторного добавления** (C7): убранный с траектории бэч исчезает с карты → Library обязан показывать все 89 (иначе он недостижим). В §5 Library = полный каталог — **сделать это явным инвариантом**.

### P2 — robustness / polish
11. Long-press **НЕ вешать** на карту-колоду практики (там свайп = листание); SVG-узлы карты — hit-test в client-px + сосуществование с pan.
12. Пустые состояния: нет `activated` → пустая колода; нет `on_path` → пустая карта.
13. Debounce/disable пунктов меню во время in-flight записи; confirm на «Убрать из траектории (деактивирует)».
14. A11y: long-press без клавиатур/SR-эквивалента — нужен альтернативный аффорданс.

**Итог консилиума:** двух-осевая модель сохраняется; критичны ровно две вещи, которые иначе **молча портят данные реальных юзеров** — (1) бэкфилл миграции `activated=isEngaged`, (2) versioned-writes вместо fire-and-forget. Остальное специфицируемо. Полный transcript: `~/Documents/AI/Claude/_inbox/consilium-2026-06-21-batch-management.md`.
