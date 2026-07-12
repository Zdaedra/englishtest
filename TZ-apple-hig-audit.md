Verified. Key facts confirmed: zero `prefers-color-scheme`, zero `color-scheme` declaration, zero `prefers-reduced-transparency`, the lone `prefers-reduced-motion` block at line 3530, the light-only `:root` token set, and `TZ-bottom-nav.md` exists at the repo root. Here is the merged ТЗ.

---

# HIG Remediation ТЗ — Executive English (iOS 26 / Capacitor)

*Lead-reviewer synthesis of four cluster audits. Scope: bring the whole web UI (React/Vite в WKWebView) to Apple Human Interface Guidelines. Все «фиксы» — это CSS/React правки в `frontend/src/**` (главным образом `index.css`). Bottom nav исключён — отдельный нативный трек (см. §5).*

---

## 1. Резюме

**Verdict: функционально приложение готово, но по HIG-полировке оно сейчас читается как web-app в обёртке, а не как нативное iOS-приложение.** Дистанция до Apple-standard средняя: нет ни одной структурной катастрофы, которая требует переписывания, но есть **четыре системных провала, которые видны на каждом экране** и два из которых — кандидаты на отклонение в App Review. Хорошая новость: почти всё стилизовано через CSS-токены, поэтому самые крупные починки — это правки в одном файле (`index.css`), дающие эффект сразу по всем 18 экранам.

**Системные темы (по убыванию leverage):**

1. **Dark Mode отсутствует полностью — P1, App-Review risk.** Подтверждено: `grep prefers-color-scheme` = 0 hits, нет `color-scheme` декларации. `:root` (index.css:5–51) задаёт только светлые токены (`--bg:#F7F7F5`, `--card:#FFF`, `--text:#111`). На устройстве в Dark Mode приложение остаётся слепяще-белым во **всех четырёх кластерах**. Это единственный самый сильный сигнал «это не настоящее приложение». Усугубляется десятками hardcoded-литералов (`#FCFCFC`, `#FFF`, `#111111`, `#F4EDEC`, `rgba(255,255,255,.x)`), которые не пойдут за токенами даже после добавления dark-блока.

2. **Dynamic Type не поддерживается нигде — P1 для accessibility-сертификации.** Каждый размер шрифта — фиксированный `px` (`.bh-title:34px`, `.train-prompt:32px`, `.field-label:13px`, …). `clamp(...vw...)` масштабируется от **viewport**, а не от настройки текста пользователя. Пользователь на Larger Text не получает изменений; местами текст падает до 7px (`OnboardingFlow`, index.css:3360) и 11.5px — ниже iOS-минимума в 11pt.

3. **Tap-target floor не установлен — P1.** В дизайн-системе нет baseline `min-height:44px`. Десятки контролов ниже 44pt: `.back-link` (~20px, используется на 4+ экранах), scrubber Playback (4px высотой, click-only), `.plan-action` (~18px), `.lang-btn` (~31px), `.sub-restore` (~33px), `.mini-play` (40px, к тому же nested `<span>`), search-clear `×` (22px).

4. **Motion и Reduce Motion почти не покрыты — P1.** Единственный `prefers-reduced-motion` блок (index.css:3530) трогает один класс `.tr-card-inner`. Параллельно крутятся: бесконечный `l3-glow` pulse на Auth-кнопке, `fade-up` на каждом `.screen`, `map-draw`, `rec-pulse` на mic-FAB, lens-pop в shell. Нет `prefers-reduced-transparency` для frosted-поверхностей.

5. **Структурные a11y/HTML-баги + отсутствие haptics — P1/P2.** Несколько `<button>`-внутри-`<button>` и `<div onClick>` на ключевых жестах (Library focus-hero, App-shell miniplayer, Training card-flip, Lesson2 phrase-card) — невидимы для VoiceOver. Haptics-плагин уже подключён и используется в Training, но **нигде больше** (mic-commit, score, verdict, save, activate, buy, tab-switch).

Дополнительно: safe-area handling частично «магическими числами» (`150px`, `+70px`) вместо `env()`; жёстко зашитый английский в `aria-label`/visible-строках на Playback и Training в приложении, которое шипит ru/es/de/fr.

---

## 2. Сквозные исправления (design-system level) — делать первыми

Эти правки в `index.css` (+ пара в `App.tsx`/`index.html`) чинят множество экранов одновременно. Это ~80% ценности всего бэклога.

### S1 · Dark Mode token pass — **P1**
- Добавить `color-scheme: light dark;` в `:root` и `<meta name="color-scheme" content="light dark">` в `index.html`.
- Добавить блок:
  ```css
  @media (prefers-color-scheme: dark){
    :root{
      --bg:#000; --card:#1C1C1E; --border:#38383A; --hairline:#2C2C2E;
      --text:#FFF; --text-2:#EBEBF0; --muted:#98989E; --faint:#6E6E73;
      --accent-tint: /* darkened */; --map-green: /* +luminance */;
      --shadow: /* softened */; --shadow-lg: /* softened */;
    }
  }
  ```
- **Sweep hardcoded-литералов** (они не пойдут за токенами): auth-gradients `#FCFCFC/#F4F7F4` (2994, 3104), `.focus-hero-play background:#fff` (545), `.auth-input` focus (3008), topic-gradient `#262626→#0E0E0F` (2538), Training `.tr-face #FCFCFC` (2905) / `.tr-stim #111111` (2948) / `.tr-judge-btn.no #F4EDEC` (3507), L3 `.l3-iconbtn/.l3-step-circle #fff` (1745, 1816), `.bh-back #fff` (1987), `.sub-buy.primary color:#fff`, все `rgba(255,255,255,.x)` veils → заменить на `var(--card)/var(--text)`/токены.
- Для baked-PNG арта с light drop-shadow (Lesson3 hero, index.css:470; row-card art) — либо `<picture>` с dark-вариантом, либо смягчить тень токеном.

### S2 · Dynamic Type / type scale → rem — **P1**
- `html{ font: -apple-system-body; }` (или `font-size:100%` + осознанный `-webkit-text-size-adjust:100%`), перевести type-scale на `rem`/`em`, чтобы body и labels реагировали на настройку текста. По-хорошему — пробросить preferred content size category через Capacitor в root `font-size`.
- **Floor 11px:** убрать все размеры <11px. Критично: 7px method-label (3360) — это симптом перегруженной плотности, лечить редизайном плотности, не уменьшением; поднять 11.5px hint (2515), 12px counters.
- Убедиться, что fixed-height контролы не клипают текст при Larger Text (дать `min-height` + wrap вместо фикс-высоты).

### S3 · Global Reduce Motion guard — **P1**
- Заменить узкий блок на 3530 глобальным:
  ```css
  @media (prefers-reduced-motion: reduce){
    *,*::before,*::after{
      animation-duration:.01ms!important; animation-iteration-count:1!important;
      transition-duration:.01ms!important; scroll-behavior:auto!important;
    }
  }
  ```
- Явно погасить бесконечные: `.l3-cta`/`l3-glow` (1954), `.rec-fab.on`/`rec-pulse` (1577), `map-draw` (2593), `fade-up`/`mini-rise`/lens-pop.
- Закрыть `scrollIntoView({behavior:'smooth'})` (Learning.tsx:263) и JS-driven анимации за `prefersReduced()` (Training уже делает это на 157 — паттерн скопировать).

### S4 · Reduce Transparency fallback — **P2**
- Нет ни одного `prefers-reduced-transparency`. Добавить:
  ```css
  @media (prefers-reduced-transparency: reduce){
    .miniplayer,.lang-btn,.tr-pill,.map-fab,<nav-glass>{
      background:var(--card)!important; backdrop-filter:none!important;
    }
  }
  ```
- Это легитимный путь — настоящего Liquid Glass в WKWebView нет, faked frosted приемлем (признано в App.tsx:46–51), но он **обязан** деградировать в opaque при Reduce Transparency.

### S5 · Tap-target baseline 44pt — **P1**
- Ввести baseline: интерактивные `button/a/[role=button]` → `min-height:44px`, hit-area ≥44×44.
- Создать **единый back-компонент** (chevron + label, ≥44pt) и заменить им все разрозненные `.back-link` / `.bh-back` / `.pb-back` / `.l3-iconbtn` — сейчас минимум 4 разных back-паттерна, часть из них ~20px. Паттерн-эталон: `.bh-back` pill (уже ≥44pt) или L3 `.l3-iconbtn` (44×44).

### S6 · Haptics на коммитах — **P2** (плагин уже подключён)
- `@capacitor/haptics` уже в проекте (Training: flip/judge). Прокинуть везде: `selectionChanged()` на toggle/pill-select; `impact({style:Medium})` на CTA-commit/tab-nav/buy; `notification({type:Success/Error})` на login/save/activate/verdict/score-arrival/restore.

### S7 · Safe-area через env(), не магические числа — **P2**
- Заменить `padding-bottom:150px` (Playback, 775) и `+70px` miniplayer-offset (1243) на `calc(env(safe-area-inset-bottom) + var(--nav-h))`. Завести общий `--nav-h` (разделяемый с нативным nav-треком).
- `vh→dvh` где остался `vh` (Training `.tr-deck min(66vh,560px)`, 2892).
- Splash/auth-screen (App.tsx:217) обернуть safe-area паддингами.

### S8 · i18n leak sweep — **P2/P3**
- Прогнать hardcoded-английский через `t()`: Playback **все** строки и `aria-label` (Back/Play-Pause/Prev/Next/Listen/Recall/Shuffle/Loop/Favorite/OF, 73–137), Training `aria-label="Mic"` (375), Library `… min` (298), Onboarding `.ob-mt-ex` примеры, Settings строки (если шипит не-админам). Anchor-слова (UNDERSTAND/WALK/…) — это контент через `tx()`, **оставить**.

---

## 3. По экранам (P1/P2/P3)

> После S1–S8 многие пункты ниже закрываются автоматически (помечены «↳ закрыт S#»). Остаются те, что требуют точечной правки React/разметки.

### Onboarding · Auth · Library · Sections

**OnboardingFlow.tsx**
- **P1 · Method-slide клипается:** `.ob-fit { height:100dvh; overflow:hidden }` (3108) + плотный контент (SVG-trail, 4 пина, 4 карточки, mnemo, бар) → на 5.4" или при Dynamic Type контент режется без recovery. → `min-height:100dvh` или `overflow-y:auto` fallback. (LAYOUT)
- **P1 · 7px label** (3360) — ↳ симптом плотности, см. S2; редизайнить плотность слайда.
- **P2 · `.ob-skip` ~38px** → `min-height:44px`. ↳ S5.
- **P3 ·** `.ob-prog-bars` → `aria-hidden` (числовой "1/3" уже озвучен).

**Onboarding.tsx (quest)**
- **P1 · `.quest-opt` без `aria-pressed`:** селект передаётся только цветом — VoiceOver не знает, что выбрано. → `aria-pressed={sel}`, single-select секции → `role="radiogroup"`. (a11y)
- **P1 · `.back-link` "Later" ~20px** → ↳ S5 (единый back-компонент).
- **P2 · Silent 2-item cap:** 3-й тап молча игнорится (Onboarding:19) → dim unselected + «Choose up to 2» helper + announce. (CONTROLS)

**AuthScreen.tsx**
- **P1 · `.auth-err` без `role="alert"`** (AuthScreen:63) — провалы логина не озвучиваются. → `role="alert"`/`aria-live`.
- **P1 · `l3-glow` бесконечный pulse** на submit (1954) → ↳ S3 (на auth-CTA — статичная тень).
- **P2 · `.auth-preview` debug-кнопка** с комментом "TEMP… remove later" (3014) рендерится в проде → удалить/спрятать за dev-flag. **App-Review polish fail.** (CONTROLS)
- **P2 · `.auth-toggle/.auth-preview` ~36–38px** → ↳ S5.
- **P2 · focus-ring только color** (3008) → добавить `box-shadow` focus-ring + токены. ↳ S1.
- **P3 ·** `.auth-brand` → `<h1>` для heading-навигации VoiceOver.

**Library.tsx**
- **P1 · Nested `<span role="button">` внутри `<button className="focus-hero">`** (289 + 301–311) — невалидный HTML, VoiceOver мис-аннонсит, fragile `stopPropagation`. → реструктура: hero как `<div>` с двумя реальными sibling-`<button>` (open / play). (a11y/CONTROLS)
- **P1 · search-clear `×` 22×22** (1484) → визуальный круг 22px оставить, hit-area расширить до 44 паддингом. ↳ S5.
- **P2 · Avatar hardcoded "AV"** (186) — ломает мульти-юзер. → инициалы из auth-user, fallback person-glyph. (CONTROLS)
- **P3 ·** metric/chevron SVG (256–282, 349) → `aria-hidden`; `lib-row` → `role="group" aria-label={section}`.

**SectionDetail.tsx**
- **P1 · `.back-link` ~20px** → ↳ S5.
- **P2 · `nav(-1)` но label всегда «Library»** (36) — врёт о назначении при deep-link/search. → `nav('/learn')` фиксированно или динамический label. (NAVIGATION)
- **P3 ·** `.app-title` длинные имена секций — разрешить wrap, `clamp()`. ↳ S2.

### Learning map · Tune · Batch home

**Learning.tsx**
- **P2 · `.mnode-label` вне hit-area:** title — sibling-`<span>` (409) вне 128px кнопки, тап по словам мёртв. → обернуть арт+label в один `<button>`. (TAP TARGETS)
- **P2 · Serpentine ±86px клипает** на ≤380px: node + halo (`box-shadow 0 0 0 11px`, 2688) + badge `right:-11px` уходят за край. → offset через `clamp()` или `@media(max-width:380px)` до ±56px; проверить, что halo активного узла не режется. (LAYOUT)
- **P2 · Map-nodes без state-trait:** `locked/active/completed` не передаётся; locked всё ещё focusable и навигирует. → `aria-label={title+', '+state}`, `aria-disabled` для locked. (a11y)
- **P2 · `.map-fab` faked glass без fallback** (2767) → ↳ S4.
- **P3 ·** count-pills (`.topic-count`/`.review-count`) → `aria-label`; `.focus-adjust` → добавить chevron; `.path-meta/.map-end` faint-контраст ниже 4.5:1 → затемнить/увеличить. ↳ часть S1.

**TunePath.tsx**
- **P1 · `.quest-opt` без `aria-pressed`/radio-checkbox** (64/77/90/103) — все 4 секции селектятся только цветом; cap-2 multi-select не озвучен. → `aria-pressed` на каждую опцию, single→`role="radio"`, secondary→checkbox, announce cap. (a11y)
- **P1 · `.back-link` ~18–20px** (50) → ↳ S5 (заменить на `.bh-back` pill).
- **P2 · Каскад-смена main focus невидим:** выбор need молча меняет селект другой секции (39–40) → подсветка-переход + haptic. ↳ S6.
- **P2 · `.tune-size` digits без label** → `aria-label`+`aria-pressed`.
- **P3 ·** inline `style={{marginTop:22}}` ×4 → класс; save-CTA опц. pin к низу с safe-area.

**BatchHome.tsx**
- **P1 · Locked-rows тап-able и навигируют:** `.bh-lesson.locked` (opacity:.6, 2120) но `<button>` без `disabled`, onClick всегда `nav(...lesson)` (166–168). → `disabled={locked}` + `aria-disabled` или guard. (CONTROLS/NAV)
- **P1 · `.bh-cover aspect-ratio:16/9`** (2001) — точный паттерн из `ios-safari-aspect-ratio-trap.md`; `<span display:block>` вероятно ок, но **проверить на реальном iPhone**; fallback `padding-top:56.25%`. (LAYOUT)
- **P2 · Два accent-системы на экране:** path = green, но `.bh-activate` CTA = bronze (2564), и paywall-CTA тоже bronze → решить одно (green=learn-identity, bronze=строго paywall). (COLOR)
- **P2 · `.bh-arrow` `→` глифы** озвучиваются «right arrow» между словами (153) → `aria-hidden` на глифы + `aria-label` на последовательность. (a11y)
- **P2 · `.bh-lesson-sub` клипается** в ru/de на 375pt (174–175, no-wrap 2137) → `-webkit-line-clamp:2`. ↳ S2.
- **P3 ·** `.l3-hint` контраст ~2.6:1 (1970) → `--muted`/темнее.

### Lessons 1/2/3 · Training · Playback

**Lesson1.tsx**
- **P1 · `.anchor` inline-toggles ~2pt padding** (CSS 1090) в тексте — почти непопадаемы. → `display:inline-block; padding:4px; margin:-4px 0`; `line-height` в `.story` ≥44pt ряды. (TAP TARGETS)
- **P1 · `.back-link` ~20px** → ↳ S5 (L3 уже использует 44×44 `.l3-iconbtn` — выровнять).
- **P2 · mic-commit без haptic** (64–85) — record start/stop + score-arrival; `haptic()` импортируется, но не вызывается. ↳ S6.
- **P2 · `rec-pulse` бесконечный** (1577) → ↳ S3.
- **P2 · `.reveal` translation контраст ~3.6:1** (1106, `--ok` 13px italic) → `--map-green-ink` или 15px. (a11y)
- **P3 ·** `.mp-pill` ~40px → padding; `.anchor` → `aria-pressed`.

**Lesson2.tsx**
- **P1 · `.pc-body` — `<div onClick>`** (171), не button — VoiceOver не видит как actionable. → `<button>` или `role="button" tabIndex aria-expanded` + Enter/Space. (a11y/CONTROLS)
- **P1 · `.back-link` ~20px** → ↳ S5.
- **P2 · `.pc-play` 42×42** (CSS 759) + icon-only без label → 44×44 + `aria-label`.
- **P2 · mic без haptic** (92–118) → ↳ S6.
- **P3 ·** `.train-counter` без `aria-live`; адопт L3 `.l3-header` для консистентности.

**Lesson3.tsx**
- **P2 · Две icon-кнопки = одно действие:** back-chevron и «menu» обе `nav('/batch/'+id)` (329, 332) — menu-глиф врёт об overflow-меню. → wire реальное действие или убрать. (NAV/CONTROLS)
- **P2 · `.l3-iconbtn/.l3-step-circle #fff`** (1745, 1816) → ↳ S1.
- **P2 · `pass-pill.ok` контраст ~3.1:1** (1650) → `--map-green-ink` на `--map-green-soft`. (a11y)
- **P2 · verdict/stage/mic без haptic** → ↳ S6 (`notification` success/error на VerdictCard mount).
- **P3 ·** `.l3-warn` chevron без действия (348–356) → убрать chevron или сделать кнопкой; `.train-prompt/counter` rem-ify, counter min 13px.

**Training.tsx**
- **P1 · Card-flip — `<div onClick>`** (332) — ядро взаимодействия невидимо для VoiceOver. → `role="button" aria-label` + key-handler или реальный `<button>` на face. (a11y)
- **P1 · Hardcoded light-литералы** (`.tr-face`, `.tr-stim`, `.tr-judge-btn.no`, dots) → ↳ S1.
- **P2 · `.tr-situ`** белый текст + text-shadow над фото-обложкой моет на светлом фото → scrim-chip / frosted-капсула как `.tr-pill`. (a11y/MATERIALS)
- **P2 · `.tr-pill` frosted без Reduce-Transparency fallback** (2923) → ↳ S4. (Примечание: `.tr-pill` — единственная **настоящая** glass-поверхность в приложении, сделана корректно.)
- **P2 · `.tr-deck` `vh` + bottom safe-area** (2892) → `dvh` + reserve `env(safe-area-inset-bottom)`. ↳ S7.
- **P2 · `aria-label="Mic"` hardcoded EN** (375) → ↳ S8.
- **P3 ·** success-haptic при score-resolve (flip/judge уже есть).

**Playback.tsx** *(самый слабый экран по controls — touch-транспорт почти нерабочий)*
- **P1 · `.scrub-track` 4px высотой, click-only** (103–104, CSS 852) — нет drag, неткаемо на тач. → ≥44pt padded hit-area (`padding:20px 0; background-clip:content-box`) + touch-drag, либо стилизованный `<input type=range>`. (CONTROLS/TAP)
- **P1 · `.tp-skip` ~30pt, `.tool` ~40pt** (CSS 879) → `.tp-skip 44×44`, `.tool min-height:48px`. ↳ S5.
- **P1 · Все строки/`aria-label` hardcoded EN** (73–137) → ↳ S8.
- **P2 · `.pb-back` ~24×24** (799) → 44×44. ↳ S5.
- **P2 · `padding-bottom:150px` магическое** (775) → `calc(env(safe-area-inset-bottom)+...)`. ↳ S7.
- **P3 ·** `.seg` ~32pt slop; tool-toggle state только цветом → `aria-pressed` + bg-fill; transport-haptics → ↳ S6.

### Subscribe · Profile · Settings · Shell

**Subscribe.tsx**
- **P1 · `.sub-restore` ~33px, muted** (2055) — Apple **требует** явный Restore Purchases на IAP-экране. → `min-height:44px`, 15px, `--text-2`/accent. (CONTROLS/TAP)
- **P2 · Secondary buy-button = `--bg`-fill** на `--bg`-фоне (2044) — почти невидим. → `--card`-fill / тинт. (COLOR)
- **P2 · `.bh-back` не nav-bar** — кастомный pill с `nav(-1)` → ↳ S5 + подтвердить swipe-back (§4).
- **P3 ·** `.sub-note` → `role="status"`; price-row wrap при больших валютах; `.sub-badge` контраст.

**Profile.tsx**
- **P1 · `.plan-action` ~18px text-only** (3380) — главный конверсионный CTA кабинета. → `min-height:44px; padding:10px 18px` + filled/tinted. (TAP/CONTROLS)
- **P1 · Language-row:** `.menu-row-static` (cursor:default) с интерактивным `.lang-btn` ~31px внутри (3025) — ниже 44pt и визуально двусмысленно. → либо вся строка открывает picker, либо `.lang-btn min-height:44px`. ↳ S5.
- **P1 · `.cab-danger` delete-account ~34px** (3064) — Apple-required, должен надёжно тапаться → `min-height:44px`. (`.auth-logout` ~43px borderline → тоже 44.)
- **P2 · «About»-row навигирует на `/profile`** (101) — на себя же. → реальный route или убрать. (NAV)
- **P2 · LangSwitcher — CSS `:hover`-меню** (3046), на тач hover нет; опции ~37px. → `min-height:44px` на `.lang-opt`; идеально — native action-sheet. (CONTROLS)
- **P3 ·** длинное имя/email без truncation-guard (h1) → `overflow-wrap:anywhere`; `.cab-ico "✦"` raw-глиф → icon-компонент + chevron; avatar → `aria-hidden`.

**Settings.tsx**
- **P1 · `.back-link` ~20px** (128) → ↳ S5.
- **P2 · `select:focus` баг:** правило `input:focus, select, textarea:focus` (1217) — `select` без `:focus` всегда в focus-стиле (выглядит вечно-сфокусированным). → починить на `select:focus`.
- **P2 · `-webkit-appearance:none` на select** (1203) убирает iOS-disclosure/picker-chrome → вернуть chevron или нативный appearance.
- **P2 · Save — inline `.btn` внизу длинной формы** (67–70) с transient "✓ saved" → auto-save on change или nav-bar trailing "Done"; `.btn min-height:44px`. (CONTROLS/NAV)
- **P3 ·** `<input type=number step=0.5>` для timing → stepper/slider + `inputMode/min/max/unit`; flat-форма → inset grouped cards; строки через `t()`.

**App.tsx (shell)**
- **P1 · `.mini-play` — nested `<span onClick>` внутри `<button className="miniplayer">`** (33–41), 40×40 (1289) — button-in-button, не focusable, без role/label. → реальный sibling-`<button>` + `aria-label` + 44×44. (a11y/TAP/CONTROLS)
- **P2 · Нет haptics** на tab-nav/buy/save/delete (lens-pop только визуал) → ↳ S6.
- **P3 ·** `.mini-title text-transform:uppercase` (1274) — вредит читаемости/VoiceOver → убрать uppercase/small-caps; splash safe-area; miniplayer `+70px` → `--nav-h` (↳ S7).

---

## 4. План по фазам

**Фаза 0 — System foundation (1 спринт, максимальный leverage).** S1 (Dark Mode + literal-sweep), S2 (rem/Dynamic Type + floor 11px), S3 (global Reduce Motion), S5 (44pt baseline + единый back-компонент). Это закрывает 4 из 5 системных тем и автоматически гасит десятки per-screen пунктов.
*Verifiable в iOS 26 sim:* Settings → Appearance → Dark; Accessibility → Larger Text (max); Reduce Motion ON; Accessibility Inspector для tap-target audit. Все четыре проверяемы без устройства.

**Фаза 1 — A11y structure + materials (1 спринт).** Структурные баги: nested buttons (Library focus-hero, App miniplayer), `<div onClick>` (Training flip, Lesson2 phrase-card) → реальные кнопки/роли. `aria-pressed`/radio-checkbox на всех `.quest-opt`/`.tune-size`/toggle. S4 (Reduce Transparency). S6 (haptics на всех коммитах). S8 (i18n leak sweep — Playback/Training).
*Verifiable в sim:* VoiceOver (rotor, trait-аннонсы); Reduce Transparency ON. Haptics — только на реальном устройстве (sim не воспроизводит Taptic).

**Фаза 2 — Layout & safe-area (0.5 спринта).** S7 (env() вместо `150px`/`+70px`, `vh→dvh`, `--nav-h`). BatchHome `.bh-cover` aspect-ratio проверка. OnboardingFlow method-slide клиппинг. Learning serpentine ±86px на узких экранах.
*Verifiable в sim:* iPhone SE / 13 mini (узкие) + Pro Max (высокий home-indicator); rotate; ⚠️ aspect-ratio trap из memory-note — **финальная проверка на реальном iPhone** (sim иногда не воспроизводит WKWebView-баг).

**Фаза 3 — Per-screen polish (P2/P3, 1 спринт).** Playback scrubber → draggable ≥44pt (самый трудоёмкий одиночный пункт). Удалить `.auth-preview` debug-кнопку. Profile «About»-route, avatar-инициалы (Library тоже). BatchHome accent-унификация (green vs bronze). Settings `select:focus` fix + appearance. Lesson3 dual-icon-buttons. Контраст-правки (`.reveal`, `pass-pill`, `.l3-hint`, faint-captions). Silent-cap feedback (Onboarding/Tune).
*Verifiable:* Accessibility Inspector contrast-checker; manual flow-walk per screen.

**Pre-submission gate:** удалить `.auth-preview`; Restore Purchases + Delete Account надёжно ≥44pt (Apple-required); прогон в Dark+Larger Text+Reduce Motion+VoiceOver на реальном iPhone.

---

## 5. Связь с нативным баром

Bottom nav в этом ТЗ **не трогаем** — он ведётся отдельным нативным треком (`TZ-bottom-nav.md`, в корне репо). Единственная точка стыка: завести общий CSS-var `--nav-h` (S7), чтобы miniplayer-offset (App.tsx:1243) и safe-area-паддинги (`.screen` :89, Playback :775) синхронизировались с финальной высотой нативного бара, а не зависели от магических `150px`/`+70px`.