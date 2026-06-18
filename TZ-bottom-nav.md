All references check out. The code confirms the panel's diagnosis exactly: double `backdrop-filter` (lines 1327-1328 + 1364-1365), `nav-gel-a/b` scaleX squash (1392-1403), 1.14-rest/1.5-pop/1.18-settle drift (1430, 146/180), `touch-action:none` drag (1331, App.tsx 107-150), search at 52px (1434), hardcoded `#8E8E93`/`#333` (1416/1440), bottom inset `+6px` (1305), and `contentInset:"always"` already present. Here is the merged decision-ready ТЗ.

---

# ТЗ: редизайн нижней навигации «Executive English» (iOS 26 Liquid Glass)

> Документ — итог консилиума (4 эксперта × 2 раунда: HIG/iOS 26, WebKit-capabilities, Capacitor-bridge, motion/haptics). Где панель расходилась — решение принято и обосновано. Спека реализуема as-is; line-numbers сверены с текущим кодом.

---

## 1. Текущее состояние и диагноз

**Что есть** (`App.tsx::FloatingNav` строки 46–211; `index.css` строки 1298–1452):
плавающий «dock» = стеклянная капсула из 3 табов (Library / Learn / Practice) + отдельная круглая кнопка поиска справа. Внутри капсулы — один скользящий «глазок» (`.nav-pill`), который `translateX`-ится по индексу активного таба, с «гелевым» `scaleX`-сжатием на ходу; активная иконка покоится увеличенной (1.14), тап запускает one-shot «pop» (1.5→1.18) через Web Animations API; палец можно тащить вдоль капсулы (`touch-action:none`, clientX→дробный индекс) со snap к ближайшему табу.

**Почему это «недостаточно близко» — консенсус панели:**

1. **Фейчится не тот слой материала (все четверо).** iOS 26 Liquid Glass определяется *рефракцией* — реальным преломлением контента, скроллящегося *за* баром, плюс спекуляр, трекающий движение. Текущий `backdrop-filter: blur+saturate` + gloss-градиент — это «frosted/vibrancy» эпохи iOS 7–15, не Liquid Glass. **WebKit #245510** (`backdrop-filter` + `feDisplacementMap`) подтверждён статусом **NEW на 2026-06-12** — настоящая backdrop-рефракция **физически невозможна в любом WKWebView**. Это не баг тюнинга, это capability-gap рендерера. Комментарий в коде (App.tsx 50–51) это уже честно признаёт.
2. **Двойной `backdrop-filter` — источник джанка (webkit + native, подтверждено в коде).** `.nav-capsule` гонит `saturate(190%) blur(26px)` (1327–1328), а вложенный `.nav-pill::before` — ещё `blur(24px) saturate(220%) brightness(1.08)` (1364–1365) в перекрывающейся области. Два backdrop-снапшота на кадр в одном регионе. Safari закэплен на 60fps даже на ProMotion → запаса нет. Вложенный blur по уже-размытому фону почти ничего не даёт визуально и стоит дороже всего.
3. **Метафора «глазка» инвертирована (HIG — оверрайд по домену).** Apple НЕ возит увеличительную линзу над плоскими табами. Индикатор выбора iOS 26 — это **glass-капсула, живущая под активным табом, которая *морфится/перетекает* к новому при переключении**; стекло *само и есть* индикатор. Скользящий-pill-как-роуминг-линза — bespoke-метафора, которой у Apple нет → читается «off-brand». (Корректный mental model: «глазок» = active-tab glass cell, которая flows к новой ячейке. Визуально на web то же, но модель верная.)
4. **`scaleX` gel-squash — мгновенный tell фейка (единогласно).** Стекло Apple морфит *форму* (блоб вытягивается к цели и сжимается обратно — surface-tension lerp), но иконки внутри *никогда не искажаются*. CSS `scaleX`-сжатие выглядит как резинка, не как стекло.
5. **Drag-to-scrub — не-HIG жест (HIG/webkit/native против; motion уступил).** В системных табах Apple жест один: tap для переключения, scroll для minimize. Drag-вдоль-бара с магнификацией Apple не использует нигде. `touch-action:none` (1331) забирает gesture-систему и дерётся со scroll-эвристиками WKWebView → лагает против 120Hz нативного жеста.
6. **Отсутствует главная подпись iOS 26 — minimize-on-scroll (HIG/webkit/native).** `tabBarMinimizeBehavior(.onScrollDown)`: капсула схлопывается до одной активной иконки при чтении, разворачивается при scroll-up. Её отсутствие — *больший* «это не iOS 26» tell, чем рецепт стекла. На web воспроизводимо на 100% (чистый transform/opacity).
7. **Нет хаптики вообще (motion/native).** `@capacitor/haptics` в package.json, но `FloatingNav` его не зовёт. Нативный таб-бар даёт selection-хаптику на каждую смену. Её отсутствие — разница между «web-демо» и «приложением».
8. **Магнификация дрейфует + размеры мимо (motion/HIG/native).** Rest 1.14 vs settle 1.18 → иконка растёт после каждого тапа и не возвращается в rest. Pop 1.5 — мультяшный (это масштаб badge, не таба). Search 52px ≈ 39pt — *под* 44pt floor (1434). Hardcoded `#8E8E93` (1416) и `#333` (1440) игнорируют dark mode.
9. **«Like Instagram» — ложный ориентир (HIG, эндорснуто webkit/native).** Instagram рендерит *кастомный непрозрачный* бар, специально *избегая* системного материала. «Как Instagram» и «как Apple Music + HIG» — противоположны. Для App-Store learning-app ориентир — **Apple Music / HIG**, не Instagram. Это надо сказать основателю прямо (см. §7).

---

## 2. Рекомендованный подход

### Решение: **HYBRID — тонкий нативный overlay-плагин «только бар» + web-fallback как полноценный baseline.**

Финальное голосование: **HYBRID единогласно** (HIG, webkit, native — HYBRID с раунда 1; motion переехал POLISHED-WEB → HYBRID в раунде 2).

**Конкретно:**

- **Нативный слой (iOS 26):** тонкий Capacitor-плагин рисует капсулу + search-island как `UIVisualEffectView(effect: UIGlassEffect())` c `.regular.interactive()`, добавленный **sibling-subview над `bridge.webView`** (НЕ `UITabBarController`). Это единственный способ получить настоящую рефракцию, touch-reactive press и спекуляр, которые WebKit не может (#245510). Fallback материала на iOS 16–25: `UIBlurEffect(style: .systemUltraThinMaterial)`.
- **Навигацией владеет ТОЛЬКО react-router.** Нативный бар — *тупой рендерер + источник событий*. Контракт one-way-truth: нативный тап → `notifyListeners("tabSelected",{index})` → JS `navigate(TABS[index].to)`; любая смена роута → `NavBar.setActive({index})` (синк для deep-links, back-swipe, `nav("/",{state:{focusSearch}})`).
- **Web-fallback бар всегда присутствует и self-contained-корректен** (Android, App-Review-safe web-билд, и iOS пока плагин не собран). Получает single-backdrop материал, minimize-on-scroll, haptics через `@capacitor/haptics`, dark mode; drag + gel-squash удалены.

### Почему HYBRID, а не альтернативы (решение конфликта native-vs-web)

| Опция | Вердикт |
|---|---|
| **Full-native `UITabBarController`** | **Reject.** Создаёт *вторую* nav-стек → десинк на deep-link / back-swipe / `state:{focusSearch}`. Нарушает single-source-of-truth. Re-архитектура (3 webview или reparenting) = 2–3 нед. |
| **POLISHED-WEB only** | **Reject как полный ответ.** Лучший *инженерный* выбор по риску (motion раунд 1), но структурно НЕ удовлетворяет дословный запрос юзера: «настоящая liquid-glass линза» + «используй НАТИВНЫЕ iOS-инструменты». Web всегда останется «frosted plastic» над hero-картинкой — ровно та жалоба, с которой всё началось. Хаптикой material-gap не закрыть. |
| **Community-плагины** (`cactuslab`, `smallcloudai`) | **Reject как primary.** Либо тянут downsides full-native, либо нет гарантии iOS 26 `UIGlassEffect`, sparse maintenance, не лягут под emerald/bronze + `focusSearch` из коробки. `cactuslab` — только как референс bridge-паттерна. |
| **HYBRID overlay (бар-only)** | **ADOPT.** Единственное, что даёт настоящее стекло БЕЗ второй nav-стека. Web остаётся приложением; нативным становится ровно один chrome-элемент, где материал Apple недостижим для WebKit. |

### Честный trade-off и трудозатраты

- **Известное ограничение HYBRID (поднял webkit раунд 2 — учесть в Swift):** нативный `UIVisualEffectView` над WKWebView сэмплит *отрендеренные web-пиксели* как backdrop, и синк сэмплинга со скроллом web **не гарантирован per-frame** — на быстром скролле стекло может отставать на 1–2 кадра. Не обещать pixel-locked рефракцию скроллящегося текста. Митигейшн: тонкий нативный ambient-слой за баром ИЛИ принять минорный лаг (всё равно бьёт CSS).
- **Эффорт:** нативный плагин option (b) — **~1 неделя** senior iOS (~250 строк Swift + ~40 строк TS-wrapper + 2 листенера в `FloatingNav`). Web-fallback фиксы — **~0.5 дня**, делать в любом случае (Android и pre-plugin билды всегда едут на нём).
- **Что переносится, а не выбрасывается:** spring/detent/press/haptic-инжиниринг из motion-брифа **релоцируется на нативную сторону**, где гонится в UIKit на 120Hz с нулевым bridge-лагом, вместо JS, дерущегося с touch-dispatch WKWebView. **Motion сохраняет владение таймингами**: контракт плагина обязан экспонировать spring-параметры и haptic call-sites (НЕ хардкодить Swift-дефолты).

---

## 3. Полная спецификация

Значения в **pt** (нативный слой) = **px** в CSS-слое (в WKWebView CSS-px ≡ pt). ×3 для @3x.

### 3.1 Геометрия и раскладка

| Параметр | Значение | Источник конфликта → решение |
|---|---|---|
| Высота капсулы | **56** | единогласно ✓ |
| Радиус капсулы | **fully-rounded** (`border-radius: 9999px` / `Capsule()`, `cornerCurve:.continuous` нативно) | true pill, future-proof против смены высоты |
| Боковой inset от краёв экрана | **21** L/R | motion/MacStories 21pt > HIG/webkit 16pt — у motion конкретный primary-source (системный бар измерен 21pt). Токен `--nav-inset`. |
| Нижний offset | `calc(env(safe-area-inset-bottom) + 12px)` — плавает ~12–16px над home-indicator, не приклеен | **NEVER hardcode** (текущий `+6px`, 1305, заменить). WKWebView-inset ≠ Safari. |
| Зазор капсула↔search | **8–10** | ✓ |
| Search-island | **круг 56** (= высота капсулы, sibling-вес) | HIG/motion 56 > native 44 / код 52. **44pt — это floor хит-таргета, не рендер-размер**; 56 тривиально его удовлетворяет. Фикс с 52px (1434). |
| Min-ширина колонки таба | **≥56** (иконки центрированы) | сильно над 44pt floor ✓ |
| Concentric inner cell | радиус = `outer − inset` = `28 − 4` = **24** | HIG-принцип concentric corners; никогда произвольный |

### 3.2 Liquid-Glass материал — нативный слой (iOS 26)

- Контейнер: `UIVisualEffectView(effect: UIGlassEffect())`, режим **`.regular.interactive()`**.
  - **Regular, не Clear** (HIG): бар сидит над легибельным текстовым контентом → HIG мандатит Regular. Не гнаться за прозрачностью ради «вау» — NN/g уже флагает legibility-провалы Liquid Glass.
  - `.interactive()` даёт touch-reactive lensing/спекуляр — это и есть *вся причина* идти нативно.
- Тинт: emerald на **низкой alpha (~8–15%)** как glass-tint, НЕ solid fill.
- Dark mode: стекло авто-адаптируется; label → `UIColor.label` / `.secondaryLabel`, brand-тинт константный (чуть desat в dark).
- iOS 16–25 fallback: `UIBlurEffect(style: .systemUltraThinMaterial)`.

### 3.3 Liquid-Glass материал — web-слой (fallback + web-сторона HYBRID)

**Жёсткое правило webkit (NON-NEGOTIABLE): ОДИН `backdrop-filter`-проход на весь dock, без перекрытия со вторым.**

```css
/* .nav-capsule — заменить строки 1326-1328 */
.nav-capsule {
  background: rgba(255, 255, 255, .44);            /* было .58 — стекло прозрачнее */
  -webkit-backdrop-filter: blur(18px) saturate(180%);
  backdrop-filter: blur(18px) saturate(180%);       /* убрать brightness() */
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,.6),             /* 1px top gloss */
    0 8px 32px rgba(0,0,0,.12);                      /* ambient */
  border: .5px solid rgba(255,255,255,.35);          /* hairline */
}

/* .nav-pill::before — УБРАТЬ собственный backdrop-filter (kill double-composite).
   Pill = чистый specular/gloss-слой над уже-размытым backdrop капсулы. */
.nav-pill::before {
  inset: 4px; border-radius: 24px;                   /* concentric 28−4 */
  background:
    linear-gradient(180deg,
      rgba(255,255,255,.65) 0%,
      rgba(255,255,255,.18) 55%,
      rgba(255,255,255,.32) 100%);
  /* НЕТ backdrop-filter здесь */
  box-shadow:
    inset 1px 1px 1.5px rgba(120,170,255,.35),       /* cool-blue rim (push) */
    inset -1px -1px 1.5px rgba(255,150,180,.30),     /* warm-pink rim */
    inset 0 1px 0 rgba(255,255,255,.6),
    0 8px 24px rgba(0,0,0,.15);
}
/* .nav-search — single backdrop, не перекрывает капсулу → ок. Match recipe. */
.nav-search { background: rgba(255,255,255,.44);
  -webkit-backdrop-filter: blur(18px) saturate(180%);
  backdrop-filter: blur(18px) saturate(180%); }
```

**Cool/warm rim — оставить (motion: «единственная самая liquid-glass деталь, что уже есть») и слегка усилить.** Спекуляр-sweep `::after` оставить, привязать сдвиг к скорости — см. §4.

**ОБЯЗАТЕЛЬНЫЙ fallback (NON-NEGOTIABLE webkit/native) — без него на iOS 16 floor бар рендерится полностью прозрачным = невидимым:**

```css
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .nav-capsule, .nav-search { background: rgba(255,255,255,.92); }
  .nav-pill::before { background: rgba(255,255,255,.98); }
}
```
Префикс `-webkit-backdrop-filter` ставить на КАЖДОЕ правило (unprefixed broadly только с 17.4).

> ⚠️ **Корректировка motion (webkit раунд 2):** НЕТ CSS-свойства, экспонирующего `UIGlassEffect` в WKWebView. `-apple-system-*` — это *шрифтовые/цветовые* keywords, не материал. Нет `backdrop-filter: liquid-glass`. Единственный системный материал на web — стандартные blur/saturate-примитивы. Не отправлять разработчика искать несуществующий CSS-hook.

### 3.4 Индикатор выбора («глазок») — переформулирован в грамматику Apple

- Это **glass-капсула под активным табом**, НЕ роуминг-линза. На смене таба **морфится между двумя фиксированными слотами**: leading-edge уходит первым, trailing-edge лагает ~60ms → блоб вытягивается через зазор и схлопывается в цели. Width-overshoot **+20%** дистанции (motion снизил с +30% — на коротких фиксированных дистанциях subtler читается чище). **Иконки внутри никогда не искажаются** (transform иконки полностью развязан с transform pill).
- **Перф-примечание webkit (friendly amendment к motion):** НЕ анимировать `width` per-frame (layout-trigger, дерётся с 60fps-бюджетом). Реализовать «fluid stretch» через `transform: scaleX()` на gloss/background-слое pill (композитный, бесплатный), иконки на своём transform. Тот же вид, compositor-safe механизм.

### 3.5 Цвета (emerald/bronze + system)

- **Active** иконка/label: бренд (текущий код использует `var(--bronze)` на active, 1426 — сохранить bronze на rim/active по вкусу бренда; emerald как primary accent на иконке). Тинт **низкоальфовым оверлеем над стеклом**, не solid.
- **Inactive:** `secondaryLabel` (≈60% label) / web `opacity: .55`, scale 1.0.
- Заменить hardcoded `#8E8E93` (1416) → `var(--ios-secondary-label)` с dark-mode значением; `#333` (1440) → `var(--ios-label)`.

### 3.6 Dark mode

```css
@media (prefers-color-scheme: dark) {
  .nav-capsule, .nav-search { background: rgba(40,40,42,.55); }
  .nav-pill::before { background: linear-gradient(180deg,
     rgba(255,255,255,.22) 0%, rgba(255,255,255,.06) 55%, rgba(255,255,255,.12) 100%); }
  /* --ios-label / --ios-secondary-label переопределить */
}
```
Нативно — авто. **Запрет hardcoded `rgba(255,255,255,…)` / `#8E8E93` / `#333`.**

### 3.7 Scroll-edge поведение (minimize-on-scroll) — MANDATORY обоими путями

- Триггер: scroll-down > **~12px** → капсула схлопывается до active-icon-only, labels fade. Web: `transform: scale(.86)` + ширина-до-active-таба (через transform, не layout) + `opacity .92`, **220ms `cubic-bezier(.4,0,.2,1)`**. Scroll-up → re-expand тем же spring.
- Нативно — зеркалит `tabBarMinimizeBehavior(.onScrollDown)`.
- **Bridge-контракт (новый, поднял motion/native):** скроллом владеет web-роутер. Native читает его через **KVO на `webView.scrollView.contentOffset`** (native-observable property, ноль per-frame bridge-трафика — рекомендация native раунд 2). Резервный путь, если KVO неудобен: web шлёт `NavBar.setScrollState({direction, offset})` (debounced).

### 3.8 Search affordance

- **v1:** нативный круг — *тупой tap-source*: фаер `searchTapped` (или `tabSelected:{index:-1}`) → web гонит существующий `focusSearch`-флоу (App.tsx 204). Никакого нативного текст-поля.
- **Нативный `.search`-role морф-в-поле — ОТКЛОНЁН для v1** (webkit/native): он требует, чтобы нативный слой владел text-input-поверхностью и бриджил keystrokes/results в web-search-UI, который уже существует → второй stateful bridge-контракт + query-sync. Нарушает «один nav-owner». Визуальный expand-морф можно зафейкать на web-стороне. Настоящее нативное поле — **v2**, после того как nav-bridge доказан.

---

## 4. Жесты и моушн

### 4.1 Drag-to-select — **ВЫРЕЗАН в v1** (motion уступил)

- **Удалить:** App.tsx 107–155 (весь drag-блок), `touch-action:none` (1331). Это #1 источник «uncanny custom widget» (native) и дерётся со scroll-эвристиками WKWebView (webkit).
- **Резон, по которому он жил, не пропал:** detent-gravity (0.65 follow / 0.35 magnetic), per-boundary haptic, rubber-band — *хорошая математика для неправильного контрола*. На web вырезаем; **нативно разрешаем как enhancement** (не v1): `UIPanGestureRecognizer` на нативном баре не имеет WKWebView-латентности и может делать magnetic detents + haptics чисто. Tap остаётся primary HIG-жестом. Контракт плагина обязан *поддержать* per-boundary `selectionChanged()`, даже если drag дремлет.

### 4.2 Магнификация — ОДНО rest-значение (motion, единогласно после раунда 2)

- **Active rest: `scale(1.12)`** (с 1.14). Inactive: `1.0`, opacity `.55`.
- **Tap-pop: `1.12 → 1.22 → 1.12`**, 280ms, `cubic-bezier(.34,1.56,.64,1)`. Overshoot +9%, возврат в rest — **никакого rest-дрейфа**. Убить 1.5 и settle-1.18.
  - Заменить вызовы `lensPop(…, 1.5, 1.18)` (App.tsx 146, 180) и search `1.55/1.2` (195–202).
  - Нативно: `symbolEffect(.bounce)` (iOS 17+), тюненный к ~+9% (дефолтный bounce овершутит сильнее).

### 4.3 Spring-тайминги перехода «глазка»

- **Native:** `CASpringAnimation` **stiffness 380, damping 30, mass 1** (≈ `.snappy`, ~380ms, ~4% overshoot). Width-stretch overshoot — looser: stiffness 300, damping 22.
- **Web:** spring через WAAPI или CSS `linear()` (оба на compositor в WKWebView, 60fps-safe). Bezier-fallback для translate: `cubic-bezier(.32,.72,0,1)` / 420ms (Apple sheet-curve). Заменить текущий `.6s var(--spring)` translate (1348) и убрать `transition: ease` где есть.
- **HIG-планка:** morph spring response ≈0.4s, damping ≈0.8 — стекло *перетекает*, не телепортируется и не gel-squash-ится.

### 4.4 Press-state (нативное ядро «iOS-feel» — addition motion для нативного пути)

- На `touchDown`: indicator `scale(0.97)`, 120ms ease-out + `.interactive()`-стекло компрессится к пальцу. Release → возврат через pop. Это **highest-value native-only деталь** — sub-100ms touch-reactive отклик, который WKWebView структурно не даёт (60fps cap + bridge-hop). Именно эти «последние 15%» — суть жалобы «not close enough».

### 4.5 Убрать gel-squash (единогласно)

- Удалить `@keyframes nav-gel-a/nav-gel-b` (1392–1403) и классы `.gel-a/.gel-b` (App.tsx 97–105). Заменяется width-overshoot fluid-stretch (§3.4), иконки не искажаются.

### 4.6 Хаптика (точные API)

**Map (motion, re-homed на нативную сторону — native раунд 2):**

| Событие | API (native, предпочтительно) | API (web-fallback) |
|---|---|---|
| Warmup | `prepare()` на `touchesBegan` (авто-warm) | `Haptics.selectionStart()` на `touchstart` |
| Смена таба тапом | `UISelectionFeedbackGenerator().selectionChanged()` **в Swift ДО bridge** (мгновенно, не ждёт JS round-trip) | `Haptics.selectionChanged()` на commit |
| Открытие search | `UIImpactFeedbackGenerator(style:.soft)` | `Haptics.impact({style: ImpactStyle.Soft})` |
| End | — | `Haptics.selectionEnd()` на `touchend` |
| Per-detent (drag) | `selectionChanged()` per boundary | — (drag вырезан в v1) |
| Удар в end-rail | **ничего** (тишина у стенки = корректно) | ничего |

- **NON-NEGOTIABLE (motion):** хаптика на каждый detent/commit с warmup. Без warmup первый тик лагает ~50–100ms и «ломается». **Никогда** не фаерить impact каждый кадр drag — iOS молча задропает (overheat Taptic Engine).
- `@capacitor/haptics` уже в package.json, сейчас не вызывается — web-путь не требует нового Swift.

---

## 5. Доступность (NON-NEGOTIABLE, HIG)

| Трейт | Поведение |
|---|---|
| **Reduce Transparency** | Стекло → solid `systemBackground`-эквивалент (`rgba(255,255,255,.92)` / dark аналог). Нативно — `UIAccessibility.isReduceTransparencyEnabled`; web — `@media (prefers-reduced-transparency: reduce)`. |
| **Reduce Motion** | Нет spring/morph/press-pop → мгновенный crossfade. Нативно — `isReduceMotionEnabled`; web — `@media (prefers-reduced-motion: reduce)`. |
| **Dynamic Type** | Бар не клипает labels; выше XL → icon-only режим. Нативно — `UITraitCollection` (тривиально); это ещё аргумент *за* HYBRID (в CSS больно). |
| **Tap targets** | Каждая колонка ≥44×44pt (по факту ≥56). Search 56pt > floor. |
| **VoiceOver** | Каждый таб — `button` с label из `t(tab.labelKey)` + trait `.selected` на активном; search — `aria-label`/accessibilityLabel. Нативный бар: корректные `accessibilityTraits`, объявление смены выбора. Web: `role="tablist"`/`role="tab"` + `aria-selected`. |

---

## 6. План реализации по фазам

### Фаза 0 — Web-fallback фиксы (~0.5 дня, делать СЕЙЧАС; едет Android + App-Review + pre-plugin iOS)
1. `index.css` 1326–1372: single-backdrop рецепт (§3.3), убрать `backdrop-filter` из `.nav-pill::before`, drop `brightness()`, opacity .58→.44.
2. Удалить `@keyframes nav-gel-a/b` + классы (1392–1403); App.tsx 97–105.
3. Search 52→56px (1434–1435); добавить `@supports not` fallback; `-webkit-` твины везде.
4. Магнификация: rest 1.14→1.12 (1430); pop 1.5/1.18 → 1.22/1.12 (App.tsx 146, 180, 195–202).
5. Dark-mode media-query; заменить `#8E8E93`/`#333` на токены (1416, 1440).
6. Bottom offset `+6px`→`+12px` token (1305); inset 21px.
7. Haptics через `@capacitor/haptics`: warmup + `selectionChanged()` на tap-commit.
8. Minimize-on-scroll (transform/opacity, 220ms) — scroll-direction детектор.
9. **Удалить drag** (App.tsx 107–155, `touch-action:none` 1331).
- ✅ **Верифицируемо в iOS 26 simulator:** раскладка, материал (frosted-уровень), morph-spring, minimize-on-scroll, dark mode, Dynamic Type, Reduce Motion/Transparency, VoiceOver.
- ⚠️ **Только на device:** хаптика (симулятор не воспроизводит Taptic Engine).

### Фаза 1 — Bridge-контракт (часть ~1-недельного нативного эффорта)
1. TS-wrapper плагина `NavBar`: методы `setActive({index})`, `setScrollState(...)` (или native KVO); листенеры `tabSelected`, `searchTapped`.
2. `FloatingNav`: 2 листенера → `navigate()` / `focusSearch`; на route-change → `setActive`.
3. `capacitor.config.ts`: `contentInset:"always"` уже есть (13) — нативный плагин добавляет `barHeight` к `webView.scrollView.contentInset.bottom`. **Один владелец inset = native; убрать CSS `padding-bottom`/bottom-инсет дока, когда нативный бар активен** (иначе три стороны — CSS + `contentInset:"always"` + overlay — дерутся за safe-area-математику).

### Фаза 2 — Нативный Swift-плагин (~250 строк, остаток недели)
1. `UIVisualEffectView(UIGlassEffect())` `.regular.interactive()` (iOS 26) / `.systemUltraThinMaterial` (16–25), sibling над `bridge.webView`, pinned к `safeAreaLayoutGuide.bottomAnchor` (−12), inset 21pt.
2. Selection pill: `UIView`+`UIGlassEffect`, `CASpringAnimation` (380/30/1), width-overshoot morph, **без scaleX-squash**.
3. Icons: SF Symbols, tint emerald/bronze, `symbolEffect(.bounce)` тюненный.
4. Haptics: `UISelectionFeedbackGenerator` pre-bridge + `prepare()` warmup.
5. Minimize: native KVO на `webView.scrollView.contentOffset`.
6. Accessibility traits, Reduce Transparency/Motion, Dynamic Type icon-only.
7. **Учесть backdrop-sampling-lag** (§2): тонкий ambient-слой за баром ИЛИ принять минорный лаг; не обещать pixel-locked рефракцию.
- ✅ **Верифицируемо в simulator:** настоящая `UIGlassEffect`-рефракция и `.interactive()`-press (симулятор iOS 26 рендерит Liquid Glass), morph, minimize, sync с web-роутером, dark mode.
- ⚠️ **Только device:** хаптика; финальное «feel» press-state на 120Hz ProMotion; реальный backdrop-sampling-lag на быстром скролле.

### Фаза 3 (v2, опционально) — нативный drag-enhancement + `.search`-role морф-в-поле
- Только после доказанного nav-bridge.

---

## 7. Риски и открытые вопросы для основателя

1. **Instagram vs Apple Music — выбрать ориентир.** Они противоположны: Instagram = кастомный непрозрачный бар, *избегает* системного стекла; Apple Music = эталон iOS 26 Liquid Glass. ТЗ выбрало **Apple Music / HIG** (для App-Store learning-app — правильно). **Подтверждаешь, что Instagram-look выкинут?**
2. **Бюджет на нативный слой: ~1 неделя senior iOS + поддержка плагина.** Без него потолок — «убедительный modern-iOS frosted-бар» (Фаза 0), но он *никогда не залинзит контент за собой* (WebKit #245510, NEW на 2026-06-12) — ровно твоя жалоба. **Финансируем нативный плагин или живём с polished-web потолком?**
3. **Drag-to-select вырезан в v1** (off-brand для таб-бара + дерётся с WKWebView). Хаптик/spring-инфра релоцируется в tap+morph+press, ничего не пропало; нативный magnetic-drag возможен как v2-enhancement. **ОК вырезать любимый «палец тащит глазок» из v1?**
4. **Search в v1 — просто кнопка-триггер существующего web-`focusSearch`** (нативное поле-морф = v2, чтобы не плодить второй stateful bridge). **ОК, что v1 не делает нативный search-field-морф?**
5. **iOS-floor и наличие Xcode/Apple Dev account.** Нативный плагин требует генерации `ios/` (`npx cap add ios`, Apple Dev + CocoaPods). bundle id `net.executiveenglish.app` — TODO-подтверждение (capacitor.config 9). **Подтверждаешь bundle id и что Apple Dev / Xcode-пайплайн готов к нативному плагину?**

---

**Файлы реализации:**
- `/Users/daedra/Documents/AI/Claude/english/frontend/src/index.css` (1298–1452: single-backdrop, drop gel-keyframes, search 56px, dark-mode, `@supports` fallback, inset/offset токены)
- `/Users/daedra/Documents/AI/Claude/english/frontend/src/App.tsx` (`FloatingNav` 77–211: удалить drag 107–155 + gel 97–105, pop 1.5/1.18→1.22/1.12, rest 1.14→1.12, haptics, minimize-on-scroll, листенеры `setActive`/`tabSelected`/`searchTapped`)
- `/Users/daedra/Documents/AI/Claude/english/frontend/capacitor.config.ts` (нативный плагин — единственный владелец `contentInset.bottom += barHeight`; bundle id подтвердить)
- Новый плагин: `/Users/daedra/Documents/AI/Claude/english/frontend/ios/App` (Swift + TS-wrapper)
---

## Зафиксированные решения основателя (2026-06-17)

- **Подход: НАТИВ (Hybrid).** Тонкий нативный слой рисует бар настоящим iOS 26 Liquid Glass; react-router владеет навигацией. Без временных решений — по максимуму на родных Apple-инструментах (UIKit/SwiftUI Liquid Glass, SF Symbols, нативные жесты, Taptic).
- **Drag-«глазок» — ОСТАВЛЯЕМ, но строго нативно** (UIPanGestureRecognizer + magnetic detents + Taptic, без лагов webview). Не временное решение — сразу «хорошо».
- **Ориентир: Apple Music / HIG.** Instagram-стиль (кастомный непрозрачный бар) отклонён.
- **Доп. директива:** продиагностировать ВЕСЬ интерфейс приложения и составить план приведения под стандарты Apple (HIG) — отдельный аудит, см. `TZ-apple-hig-audit.md`.
