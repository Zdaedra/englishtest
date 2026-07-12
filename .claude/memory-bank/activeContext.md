# Active Context: english

> **Текущий фокус. Обновляется в КОНЦЕ каждой сессии.**

**Last updated:** 2026-07-02

## Current focus

**RETENTION-КОНТУР + КОНВЕРСИЯ ДОБАВЛЕНЫ (2026-07-02, локально, НЕ закоммичено).** По итогам анализа
«продукт × рынок» (Fluently — главный конкурент по ЦА; связка native-фразы+мнемоника+SRS+STT не занята никем)
реализованы 6 фич: серверный стрик с freeze (`/api/progress/streak`), due-персонализация daily-пуша,
пословная подсветка ответа (interim + дифф эталона), weekly summary (`/api/training/weekly` + карточка),
placement-тест «Проверь лигу» (/league, 7 ситуаций, конверсионный крючок), Call Analyzer-lite
(`/api/analyzer/call` + /analyze, AI-план, hand-off в /import). Backend 160 passed, tsc/build чистые.
Детали — в progress.md за 2026-07-02. **Следующий шаг:** коммит (дерево содержит и другие незакоммиченные
изменения — разнести по коммитам), проверка на реальном iPhone (Web Speech interim, пуш), деплой.

**✅ ВСЕ 7 PRESENCE-НАПРАВЛЕНИЙ ЗАПОЛНЕНЫ (2026-06-02). Корпус 89/89 батчей на диске.**
Консилиум-луп (Opus 4.8 ↔ GPT-5 → синтез) завершён. Раскладка: 13 бизнес-эталон (01–13, на проде, НЕ тронуты) +
11 charisma + 10 flirt + 12 intimacy + 11 leadership + 11 composure + 10 gravitas + **11 stage (79–89)**. Бизнес-эталон
01–13 проверен `git status`: 0 M/D (все presence-файлы untracked-новые). Транскрипты консилиума: `_inbox/consilium-2026-06-01-*`.
**Следующий шаг (НЕ в этой сессии):** загрузить presence-батчи в БД (`content.upsert` / `app.seed`) с проставлением
`section` по slug-префиксу, прогреть аудио-кэш, ревью качества вживую. UI-доработка тестов/практики — в отдельной spawn-сессии.

**КОНТЕНТ-СТРАТЕГИЯ ПЕРЕСОБРАНА ПОД EXECUTIVE PRESENCE (2026-06-01, вечер).**
Ключевой тезис (правка Алексея + консилиум Opus↔GPT): «English Executive» — НЕ «учить язык» и НЕ
survival/transactional English (иммиграция, отель, такси, возвраты, симптомы — проваливает суть). Это
тренажёр для тех, кто УЖЕ свободно говорит, чтобы оттачивать регистр, формирующий **executive presence**
— как тебя ВОСПРИНИМАЮТ (авторитет, харизма, гравитас, теплота, влияние, владение собой, статус, доверие)
в высокоставочных ЧЕЛОВЕЧЕСКИХ моментах. Тест бетча: «меняет ли владение 9 фразами ТО, КАК человека
воспринимают — или просто решает бытовую задачу любого говорящего?» Если второе → CUT.

**Апгрейд механики зон:** 3 зоны теперь НЕ «мягко→жёстко», а **регистровый диск** (выбор по чтению
комнаты): **Тепло** (расположить/снять угрозу) · **Спина** (прямо, держать позицию без агрессии) · **Вес**
(статус/гравитас). Существующие 13 бизнес-бетчей — на эскалации интенсивности; новые presence-направления
— на этом диске.

**Settled карта (7 presence-направлений + эталон, ~76 бетчей):** Бизнес-коммуникация (эталон, 13 ✅) ·
1) Харизма 11 ✅ (бетчи 14–24) · 2) Флирт и притяжение 10 ✅ (25–34, магнетизм из уверенности, НЕ pickup) ·
3) Близость и узы 12 ✅ (35–46, presence под эмоц. нагрузкой, НЕ разговорник свиданий) · 4) Лидерство без
должности 11 ✅ (47–57) · 5) Самообладание и достоинство 11 ✅ (58–68) · 6) Гравитас в кризисе 10 ✅ (69–78) · 7) Сцена и публичность 11 ✅ (79–89).
Наполнение — побетчным консилиумом (Opus ↔ GPT → кросс-критика «нативно/presence-grade?» → синтез → JSON в
`backend/content/`). Транскрипты: `_inbox/consilium-2026-06-01-*`. Бетчи 14–18 (Travel survival) УДАЛЕНЫ.
**Прогресс наполнения: 89/89 на диске — ЗАВЕРШЕНО** (13 бизнес + 11 charisma + 10 flirt + 12 intimacy + 11 leadership + 11 composure + 10 gravitas + 11 stage).

**Решение пользователя (scope финала): ПОЛНЫЙ размер ~21** — оба последних направления целиком, каждый бетч развести по углу от ближайших Leadership/Composure (не дублировать).

**План «Гравитас в кризисе» (section "gravitas", slug gravitas-N), ~10 — угол: ВЕС/КОМАНДА на максимальном давлении (war-room/ЧП/катастрофа/hot seat), НЕ повседневное лидерство и НЕ личная защита достоинства:**
1) Взять командование, когда всё горит · 2) Говорить с весом, когда внутри страшно · 3) Сделать необратимый
звонок под неопределённостью · 4) Не дрогнуть под шквалом враждебных вопросов · 5) Признать катастрофу, не
теряя командования · 6) Держать рамку против ранга/угрозы/силы · 7) Дать уверенность, когда исход неизвестен ·
8) Остановить опасную эскалацию словом · 9) Командовать через спокойствие и экономию слов · 10) Завершить кризис,
посадить самолёт.

**«Сцена и публичность» (section "stage", slug stage-N) — ЗАВЕРШЕНО 11/11, файлы 79–89:**
1) Открыть выступление (79) · 2) Командовать сценой (80) · 3) На камеру/в записи (81) · 4) Сценический страх вживую (82) ·
5) Враждебные вопросы из зала (83) · 6) Восстановиться после провала (84) · 7) История, которая держит зал (85) ·
8) Закрыть мощно, дать унести (86) · 9) Под софитами/вниманием прессы (87) · 10) Личный момент с большой аудиторией (88) ·
11) Импровизировать, когда план рухнул (89).

**ВАЖНО — бизнес-бетчи 01–13 (на проде, эталон) НЕ трогать.** За сессию только СОЗДавались новые файлы (charisma/flirt/intimacy/leadership), ни одной перезаписи/удаления 01–13. Проверено git: всё untracked-новое.

**Параллельная задача (spawn):** UI-доработка системы тестов и практики вынесена в отдельную сессию (чип). Деплой на Hetzner — позже, ТОЛЬКО с подтверждением пользователя, без превью.

**План «Самообладание и достоинство» (section "composure", slug composure-N), 11 бетчей:**
1) Не дать себя спровоцировать (не клюнуть на наживку) · 2) Принять оскорбление/выпад с достоинством ·
3) Держаться, когда унижают публично · 4) Сохранить лицо после ошибки/конфуза · 5) Не оправдываться под давлением ·
6) Уйти из токсичного разговора с достоинством · 7) Держать паузу под напором (не отвечать сразу) ·
8) Ответить на неуважение, не опускаясь · 9) Остаться собой под лестью/манипуляцией · 10) Сказать «не знаю»
без потери лица · 11) Держать достоинство в проигрыше/отказе/когда обошли.

---

### Прежний UI-фокус
**Экран Урок 3 «Тесты» — премиальный редизайн Apple-Music/Fitness+ (фирменный зелёный), задеплоен.**
`pages/Lesson3.tsx` переписан презентационно (логика 3 этапов не тронута): градиентный фон `.l3-screen`
(#FCFCFC→#F4F7F4), хедер из 2 круглых кнопок 44×44, hero (УРОК 3 зелёным + «Тесты» 40px + `<Art3D/>` —
SVG soft-3D зелёный речевой пузырь+карандаш), `ExamTrack` → круги 40px с активным зелёным + play-бейджем и
пунктиром, warn-card вместо красного текста (щит+Safari/Chrome зелёным+chevron), `StageIntro` → task-card
(radius 28, иконка-волна, body 18px, декоративная `<WaveDeco/>`) + зелёная CTA с glow + хинт-наушники. Новые
иконки `IconMenu/IconShield/IconHeadphones`. Весь блок `.l3-*` в `index.css`, зелёный = `var(--map-green)`.
3D-иллюстрация — **настоящий рендер через gpt-image-1** (матовый зелёный речевой пузырь+карандаш,
transparent PNG 160 КБ в `frontend/public/art/lesson3-hero.png`, отдаётся на `/art/lesson3-hero.png`;
`Art3D` = `<img>`). Бандл `index-D6aXbLaM.js`/`index-JwYmchnE.css`.

Предыдущий фокус: нижняя навигация → плавающая «Apple Music» + рабочий поиск по библиотеке. Таб-бар заменён на два отдельных плавающих стеклянных элемента: **капсула**
(Библиотека/Практика/Профиль, `App.tsx::FloatingNav`, 280px=72% vw, h70, r35, blur(22px), `rgba(255,255,255,.82)`,
тень `0 12 36 .10`, без рамок) + **отдельная круглая кнопка поиска 70×70** справа. Активное состояние —
**liquid-glass pill** (`.nav-pill::before`, inset 6px → 58px, r29, градиент-глянец `.96→.66` + blur(24px) +
border `rgba(255,255,255,.85)` + inset-блик/тень + drop `0 8px 22px .12`), приподнятый отдельный стеклянный
объект внутри капсулы (НЕ плоская заливка); радиусы вложены 35=29+6, у капсулы снят `overflow:hidden`.
Активный таб `#2B2118`, неактивные `#8E8E93`, поиск `#111`. Пружинно скользит между табами (translateX по
`--active`); внешний слой `.nav-pill` позиционирует, стекло в `::before` — поэтому выравнивание точное.
Таб «Playback» убран (плеер — через мини-плеер). Кнопка поиска раскрывает строку поиска в `Library.tsx`
(фильтр по title/preview/theme/anchors, «Найдено · N»/«Ничего не найдено»/«Отмена»). Проверено вживую
(Playwright): геометрия по ТЗ, скольжение таблетки, фильтр. Бандл `index-CD23gvtx.js`/`index-ClOvV7-I.css`;
backend не менялся. ⚠️ iPhone: авто-фокус строки поиска может не поднять клавиатуру сразу (фокус вне жеста).

Предыдущий фокус (тот же день): **Урок 3 «Тесты» — финал переделан в 3-этапный экзамен.**
Вместо одного random-stop+пересказ теперь **три строго последовательных этапа** (открываются по очереди,
проход = средний ≥8/10 = 80%, каждое слово ≥2 раз в этапе):
**Этап 1 — Полный пересказ** (назвать все якоря по порядку, `scoreSequence`, 2 пересказа);
**Этап 2 — По мнемо-основе** (история играет и замирает НА КАЖДОМ якоре → «стоп» → назвать фразу,
`scorePhrase`, 2 полных прохода, «Пропустить»=0);
**Этап 3 — Фраза → якорь** (звучит англ.фраза → назвать её якорь, новый `scoreAnchor`, каждая фраза 2×).
Возле каждого этапа — **процент** + «Пересдать» (<80%) либо «Дальше»; все три ≥80% → `l3_passed` (батч
закрыт, следующий на пути открыт). Степпер `ExamTrack` сверху, прогресс возобновляется на первом
несданном этапе. **Новое в backend:** `scoring.py::score_anchor` (строковое сходство, без LLM, без
`_MIN_TOKENS`) + `POST /api/training/score-anchor` (пишет `PhraseAttempt`, но НЕ трогает per-phrase EWMA).
**Frontend:** `api.scoreAnchor`/`AnchorScore`, флаги `l3_s1`/`l3_s2` в `progress.ts`, полный реврайт
`pages/Lesson3.tsx` (`scoresRef` рефом для среднего; replay этапа 2 через `replaySignal`-эффект +
`seek(0)+resume`, т.к. `play("full")` лишь тогглит уже загруженный layout; `stageRef`-гарды в audio-колбэках).
Деплоен бандл `index-DvA5O4lb.js` / `index-DziEdFDM.css`; `english_app` пересоздан, cookie-гейт цел,
маршрут score-anchor подтверждён в контейнере. ⚠️ iPhone PWA — возможен 1 reload для сброса оболочки.

Предыдущий фокус (тот же день): редизайн пути обучения `/#/learn` (`Learning.tsx`) в спокойную карту-дорогу
с measure-based ортогональной SVG-линией и посегментной зелёной заливкой, без геймификации; бандл
`index-D324m8LI.js`/`index-ZXUakjat.css`.

Предыдущий фокус (тренировка): линейный flow из 3 уроков на `BatchHome` (`batch/:id`) — **Урок 1
Мнемоническая основа** (слушать, тапать якоря, мягкий пересказ→LLM, без хард-гейта), **Урок 2 Фразы**
(якорь→фраза, перезапуск истории в уроке, Тест B drill, мягкий гейт mean≥6), **Урок 3 Тесты** (история
замирает на ~30% якорей → назвать фразу iOS-safe по тапу; финал — пересказ последовательности =
**хард-гейт** passed≥7 → `l3_passed`). Запись микрофона строго по тапу (`RecFab`). `scoring.py::
_PHRASE_SYSTEM` принимает сжатые формы как 9-10 при сохранённом ключевом глаголе.

## Recent changes (last 1-2 sessions)
- **Design Book + DESIGN.md (2026-06-01):** единый визуальный гид `frontend/public/design-system.html`
  (11 разделов, зеркалит токены `index.css`) → захостен на `executive-english.net/design-system.html` (за гейтом);
  + `DESIGN.md` (корень репо) — текстовая выжимка стиля для ИИ-инструментов (Cursor/Codex/Claude). **При дизайне
  новых экранов — сверяться с DESIGN.md / открывать гид.**
- **Карточка батча BatchHome редизайн (2026-06-01):** `/batch/:id` в новый зелёный стиль (hero-обложка, тег
  «Урок N» = позиция в пути, карточка-цепочка якорей, «ЭТАПЫ УРОКА» с premium-карточками этапов, зелёная CTA).
  `.bh-*` классы, логика уроков не тронута. Бандл `index-BUY7qw45.js`/`index-Fv4qdEh-.css`.
- **3D-объект Урок 3 hero через gpt-image-1 (2026-06-01):** см. ниже.
- **Экран «Тесты» (Урок 3) редизайн (2026-06-01):** Apple-Music/Fitness+ в фирменном зелёном. `Lesson3.tsx`
  презентационно переписан (хедер-кружки, hero+`Art3D` SVG, `ExamTrack` с play-бейджем+пунктиром, warn-card,
  task-card+`WaveDeco`, зелёная CTA с glow, хинт). `+IconMenu/IconShield/IconHeadphones`, блок `.l3-*` в CSS,
  фон-градиент. Логика 3 этапов не тронута. Бандл `index-SEJ4cZ7R.js`/`index-CRBSjDze.css`. 3D — пока SVG. ✅
- **Нав-полировка (2026-06-01):** бар тоньше (Apple-Music: капсула 70→56px r28, search 70→56); стекло
  прозрачнее (capsule/search bg .82→.58, blur26; pill .96→.66 → .8→.4 + brightness/блик) → frosted-контент
  просвечивает; pill между табами медленнее (.42→.6s); search press: кнопка ×1.2 (>бар) + лупа ×1.55.
  Мини-плеер/паддинги подвинуты. Бандл `index-CnmOqCE7.js`/`index-B2EzOhD8.css`. Потолок iOS — настоящий
  Liquid Glass (преломление) только в нативе. ✅
- **Поиск 2 блока + линза-поп + drag-жест (2026-06-01):** (1) Поиск Library теперь по батчам И фразам —
  новый backend `GET /api/batches/phrases` (плоский индекс, объявлен до `/{batch_id}`), `api.listPhrases()`,
  в `Library.tsx` ленивая загрузка + два блока «Батчи · N»/«Фразы · N» (тап фразы → её батч). (2) Press-фикс:
  активная иконка постоянно крупнее (`scale(1.18)`) + one-shot «поп» через WAAPI на `click` (`lensPop`) —
  видно при любом тапе (старый hold-press был невидим на быстром касании). (3) Drag-жест по бару: pointer-DnD
  на `.nav-capsule`, pill едет за пальцем (`--active` дробная, `posFromX`), линза на ближайшем табе, release→nav;
  `touch-action:none`, `setPointerCapture` в try/catch, тап не конфликтует. Бандл `index-DGyK2Kig.js`/
  `index-DR6N1sal.css` (frontend+backend). ✅
- **Нав: зелёный акцент + Liquid-Glass press (2026-06-01):** активная иконка → фирменный изумруд
  `var(--map-green)` #1C8C63 (был графит). Усилено стекло pill: `::after` блик-купол + хроматическая кайма
  в box-shadow (`rgba(120,190,255)`/`rgba(255,150,205)`). **Press-эффект** через pointer-события:
  `.nav-tab.pressing` ×1.06/иконка ×1.24, `.nav-search.pressing` ×1.1/иконка ×1.2. **Желейное перетекание**
  pill — keyframes `nav-gel-a/-b` (scaleX 1.16) на смене таба (`moveTick`). ⚠️ Исследование: истинное
  backdrop-преломление (SVG `feDisplacementMap`) — Chromium-only, в iOS Safari НЕ работает (баг WebKit
  #245510); на iOS сделана достижимая имитация. Бандл `index-Djb4qgB1.js`/`index-Cj73imAe.css`. ✅
- **Liquid-glass активный pill (2026-06-01):** активный таб нав-капсулы из плоской серой заливки → отдельный
  стеклянный объект `.nav-pill::before` (inset 6px=58px, r29, градиент `.96→.66`, blur(24px), border
  `rgba(255,255,255,.85)`, inset-блик + drop-shadow). С капсулы снят `overflow:hidden` (радиусы вложены
  35=29+6). Active `#2B2118` (weight 680), inactive `#8E8E93`, search `#111`. Бандл `index-CTpalwlr.js`/
  `index-J6PFrACi.css`, деплой только `english_app`. ✅
- **Плавающая навигация Apple Music + поиск (2026-06-01):** `BottomNav`→`FloatingNav` в `App.tsx`
  (капсула 3 таба + отдельная кнопка поиска, стекло/тени/без рамок, скользящая таблетка `.nav-pill` через
  `translateX(var(--active)*100%)`, прозрачные L/R-бордеры+`background-clip` для inset). Поиск в `Library.tsx`
  (открывается из кнопки через `nav("/",{state.focusSearch})`, фильтр грида). `IconSearch` добавлен.
  Таб Playback убран. Проверено Playwright (геометрия по ТЗ, скольжение, фильтр). Бандл
  `index-CD23gvtx.js`/`index-ClOvV7-I.css`, деплой только `english_app`, гейт цел. ✅
- **Урок 3 → 3-этапный экзамен (2026-06-01):** финал `pages/Lesson3.tsx` переписан из random-stop+пересказ
  в три строго последовательных этапа (Полный пересказ → По мнемо-основе → Фраза→якорь), проход каждого
  средний ≥8/10 (80%), каждое слово ≥2 раз. Backend: `scoring.py::score_anchor` (строковое сходство, без
  LLM/`_MIN_TOKENS`) + `POST /api/training/score-anchor` (НЕ трогает EWMA). Frontend: `api.scoreAnchor`/
  `AnchorScore`, флаги `l3_s1`/`l3_s2`, `ExamTrack`-степпер, `.exam-track`/`.verdict-pct` в `index.css`.
  Тонкости: `scoresRef` рефом (переживает audio-колбэки); replay этапа 2 — `replaySignal`-эффект +
  `seek(0)+resume` (НЕ `play("full")` — тогглит загруженный layout); `stageRef`-гарды в `onTick/onStoryEnded`.
  Деплой: build → rsync → пересборка только `english_app`; бандл `index-DvA5O4lb.js`/`index-DziEdFDM.css`,
  маршрут score-anchor подтверждён в контейнере, гейт цел. ✅
- **Фикс «Проверь фразы» Урок 2 (2026-06-01):** убрал авто-диктовку фразы в дрилле (был `useEffect` авто-play
  как shadow-подсказка) — теперь только якорь, фраза по явному тапу «Подсказать фразу». Бандл `index-CO2kef8u.js`.
- **Редизайн пути обучения в карту-дорогу (2026-06-01):** консилиум (Opus+GPT+Claude) сравнил мой
  прогресс-путь (узлы сбоку от прямого пунктирного хребта) с референсом «Communication Games» (узлы на
  плавной связной линии) → синтез «спокойная премиальная карта без геймификации». `MapTrack` в
  `pages/Learning.tsx` переписан с uniform-`frac` на **measure-based ортогональную SVG-дорогу с точечной
  посегментной зелёной заливкой**: сигнатура `{done, sig}` (было `{frac, sig}`), state `{full, done}`,
  `done`=число пройденных ЦЕЛЫХ сегментов (`reached` из `stateOf!=="locked"`). Путь — округлые
  L-колена (Q-углы, R=16). Фикс бага недолёта (uniform frac не дотягивал до активного узла, т.к. первый
  сегмент длиннее из-за «пузыря») — посегментная заливка, проверено `getPointAtLength` (зелёный кончается
  на center-x активного узла, 2px под верхом). Анимация — CSS `@keyframes map-draw` (dashoffset 1→0,
  pathLength=1). `index.css`: `.map-track-done` animation, locked-узлы чётче (opacity .82, grayscale(1)
  saturate(.4), overlay .16, badge .5). Верхний прогресс-бар убран → «Пройдено N из M», FAB scroll-aware.
  Геймификации нет. Верификация: vite dev на свежем origin (без SW), прод-данные через proxy, localStorage
  посеян через Chrome MCP, навигация на хеш-роут `/#/learn`. Деплой: build → rsync → пересборка только
  `english_app` (exit 0, чужие не тронуты), бандл `index-D324m8LI.js`/`index-ZXUakjat.css` в контейнере,
  `/login`→200. ✅ ⚠️ iPhone PWA — нужен 1 reload для сброса старой оболочки.
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
