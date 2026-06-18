# ТЗ: Executive English — нативное приложение для iPhone (App Store)

> Статус: черновик v1 · 2026-06-09
> Цель документа: дать исполнимое техническое задание на упаковку текущего веб-продукта в нативное iOS-приложение и публикацию в App Store.

---

## 0. Резюме и решение

Берём существующий React/Vite-фронтенд и оборачиваем его в нативную iOS-оболочку через **Capacitor**. Переиспользуем ~100% UI и весь бэкенд. Доращиваем то, чего требует App Store и нативная среда:

1. **Сетевой слой** — абсолютный base URL API (новый поддомен `api.executive-english.net`).
2. **Авторизация: cookie → Bearer-токен** (dual-mode: веб остаётся на cookie, нативка — на токене в Keychain).
3. **Apple In-App Purchase (StoreKit 2)** вместо Stripe — подписки `core`/`ai`, серверная валидация, маппинг на `User.plan`.
4. **Микрофон/аудио** — нативные разрешения + переход на MediaRecorder→server-STT (Web Speech в WKWebView нет).
5. **Удаление аккаунта в приложении** (требование Apple 5.1.1(v)).
6. **Приватность** — privacy policy, App Privacy labels, строки usage-description.
7. **Нативная полировка** — иконка, splash, haptics, статус-бар, safe-area.

**Почему Capacitor, а не альтернативы** — см. §3.

**Оценка по времени** (один разработчик): MVP в TestFlight ~2 недели, готовность к сабмиту ~4–5 недель. Детали — §8.

---

## 1. Цель и охват

**Цель:** выпустить Executive English как нативное приложение в App Store (iPhone, портрет), монетизация через подписки Apple, без потери текущего функционала и дизайна.

**В охвате:**
- iOS-приложение (iPhone, iOS 16+; обоснование порога — §5.5).
- Платная подписка через Apple IAP.
- Все текущие экраны: онбординг, Библиотека, Обучение, Практика (свайп-тренажёр + голос), Кабинет.
- i18n (ru/es/de/fr) — уже готов.

**Вне охвата (этого этапа):**
- iPad-оптимизация (работает в режиме совместимости; нативный iPad-layout — позже).
- Android (Capacitor позволит добавить позже малой кровью).
- Перевод **контента БД** (`MnemoStory.story_ru`, названия бэтчей) на es/de/fr — отдельная фаза, не блокирует релиз.
- Веб-платежи (Stripe на сайте) — отдельно, если понадобятся.

---

## 2. Текущее состояние (база, от которой отталкиваемся)

| Слой | Технология | Факт |
|---|---|---|
| Frontend | React 18 + Vite + TS, hash-router, кастомный i18n (ru/es/de/fr), service worker | PWA, деплоится как статический `dist` |
| Сеть | `fetch("/api/...")` — **относительные пути** | Работает только same-origin (через Caddy/Vite-proxy) |
| Auth | Signed-cookie `eng_auth` (httponly, samesite=lax) | Завязано на same-origin; в нативном WKWebView ненадёжно |
| Backend | FastAPI + SQLModel + SQLite, Docker, Caddy | Hetzner, `executive-english.net`, multi-tenant |
| Подписки | `entitlements.py` (free/core/ai) | Только пакетирование; **платежей нет** (Stripe не внедрён) |
| AI | OpenAI: STT, скоринг, AI-коуч, генерация аудио/обложек | Аудио ответа пользователя уходит в OpenAI STT |
| Микрофон | `webkitSpeechRecognition` (on-device, Safari/PWA) + MediaRecorder→server-STT fallback | В WKWebView Web Speech **недоступен** → останется только fallback |
| CORS | `allow_origins=[localhost:5173]` | Под нативный origin не настроен |

**Вывод:** фронт и бэк качественные и почти готовы; нативная упаковка требует адресных изменений в 6 местах (сеть, auth, платежи, микрофон, удаление аккаунта, приватность), не переписывания.

---

## 3. Архитектурное решение

### Выбор: Capacitor (рекомендуется)

[Capacitor](https://capacitorjs.com) — нативная оболочка (Xcode-проект) с WKWebView, в которую кладётся собранный `frontend/dist`. Нативные возможности (IAP, микрофон, push, haptics, Keychain) подключаются плагинами; JS-код остаётся тем же.

**Плюсы:**
- Переиспользуем 100% React-кода, дизайна, i18n.
- Реальный нативный бинарь → проходит в App Store (PWA в App Store не публикуются).
- Один кодстек на iOS + потом Android.
- IAP/микрофон/push через готовые плагины.

**Минусы / на что заложиться:**
- WKWebView ≠ Safari: нет `webkitSpeechRecognition`, нюансы аудио и cookie.
- Apple-ревью смотрит на «webview-обёртки» (Guideline 4.2) — закрываем нативными фичами (IAP, микрофон, push, офлайн).

### Отклонённые альтернативы

| Вариант | Почему нет |
|---|---|
| **Чистый PWA «на домашний экран»** | Не попадает в App Store, нет IAP/нормального push, нет витрины — для коммерческого запуска не годится. |
| **Полный нативный rewrite (SwiftUI)** | 2–3 месяца работы ради UI, который уже есть и отполирован. Не оправдано на этой стадии. |
| **React Native rewrite** | Переписывание всего фронта; теряем готовый веб + единый код с сайтом. |

---

## 4. Что переиспользуется без изменений

- Весь React-UI и CSS (онбординг, Практика, карточки, кабинет, дизайн-система).
- i18n-движок и локали ru/es/de/fr.
- Вся бизнес-логика бэкенда: бэтчи, фразы, мнемы, скоринг, AI-коуч, SRS, entitlements.
- Контент (89 бэтчей), генерация аудио/обложек.
- Деплой бэкенда (Hetzner/Docker/Caddy) — добавляем только поддомен, CORS и пару эндпоинтов.

---

## 5. Рабочие потоки (детально)

### 5.1 Capacitor-оболочка (frontend)

**Задачи:**
- Добавить `@capacitor/core`, `@capacitor/cli`, `@capacitor/ios`; `npx cap init`.
- `capacitor.config.ts`: `appId = net.executiveenglish.app` (пример), `appName = "Executive English"`, `webDir = "frontend/dist"`, `ios.contentInset = "always"`, `backgroundColor`.
- **Router:** hash-router совместим с Capacitor (file/scheme origin) — оставляем как есть. Проверить, что deep-link не нужен на старте.
- Плагины: `@capacitor/preferences` (или Keychain) для токена, `@capacitor/haptics`, `@capacitor/status-bar`, `@capacitor/splash-screen`, `@capacitor/app` (lifecycle), `@capacitor/keyboard`.
- Build pipeline: `vite build` → `npx cap sync ios` → открыть в Xcode.
- Service worker: в нативе ассеты локальные; SW можно отключить в нативной сборке (определять `Capacitor.isNativePlatform()`), API-кэш не нужен.

**Acceptance:** приложение запускается на симуляторе/устройстве, показывает текущий UI, ассеты грузятся из бандла.

### 5.2 Сетевой слой: абсолютный base URL

**Проблема:** `fetch("/api/...")` в нативе резолвится в `capacitor://localhost/api` → 404.

**Задачи:**
- Ввести `API_BASE` (env `VITE_API_BASE`): для веба — `""` (относительный), для нативы — `https://api.executive-english.net`.
- Обернуть все `fetch` в `apiUrl(path)` (одна правка в `api.ts` + аудио/обложки URL'ы, которые приходят как пути — добавить base).
- Поднять поддомен `api.executive-english.net` → тот же бэкенд (Caddy reverse-proxy), TLS.

**Acceptance:** нативка ходит на `api.executive-english.net`, обложки/аудио грузятся.

### 5.3 Авторизация: cookie → Bearer-токен (dual-mode)

**Проблема:** httponly-cookie в кросс-origin WKWebView ненадёжен (ITP, SameSite, блокировка сторонних cookie). Нужен явный токен.

**Backend (`auth.py` / `routers/auth.py`):**
- На `register`/`login` возвращать в теле `{ token: <signed> , ...user }` **дополнительно** к cookie (cookie оставляем для веба).
- Auth-middleware: принимать токен из `Authorization: Bearer <token>` **или** из cookie (что есть). Тот же `make_session`/verify, просто другой транспорт.
- TTL токена 60 дней (как cookie), refresh при `me`/активности (опц.).
- Logout: на нативе достаточно стереть токен на клиенте (server-side blacklist не обязателен на старте).

**Frontend (`api.ts`, `AuthContext`):**
- После login/register сохранять токен в `@capacitor/preferences` (или Keychain через `capacitor-secure-storage`).
- В `fetch` добавлять `Authorization: Bearer` при наличии токена (нативка).
- На старте — читать токен, дергать `me`.

**Acceptance:** на устройстве логин/сессия живут после перезапуска приложения; веб не сломан.

### 5.4 Apple In-App Purchase (StoreKit 2) + серверная валидация

> Это самый объёмный поток. Apple **обязывает** продавать цифровые подписки только через IAP (Guideline 3.1.1). Stripe для iOS — нельзя.

**Продукты (App Store Connect):** авто-renew subscriptions, одна группа «Executive English»:
- `core_monthly`, `core_yearly`
- `ai_monthly`, `ai_yearly`
- (опц. вводный оффер / триал)

Цены/копирайт — решение продукта (см. §11). `free` остаётся бесплатным дефолтом.

**Клиент:** вариант на выбор —
- **(A) RevenueCat** (рекомендую для скорости): SDK + Capacitor-плагин, сам валидирует чеки, отдаёт «активные entitlements», вебхук на наш бэкенд. Меньше серверного кода, кросс-платформенно. Минус — внешняя зависимость + % с оборота на масштабе.
- **(B) Нативно**: `@capacitor-community/in-app-purchases` (StoreKit 2) + наша серверная валидация через **App Store Server API** / `verifyReceipt` + **App Store Server Notifications v2** (вебхук на продления/отмены/refund). Без внешних зависимостей, больше кода.

**Backend:**
- Эндпоинт `POST /api/billing/verify` — принимает транзакцию/чек, валидирует у Apple, выставляет `User.plan` (`core`/`ai`) и срок действия.
- Вебхук `POST /api/billing/apple-notifications` (ASSN v2) — продление/expire/refund/grace → обновляет `plan`.
- Новые поля `User`: `plan_source` (`apple`|`manual`), `plan_expires_at`, `apple_original_tx_id`.
- При истечении — даунгрейд в `free` (entitlements уже это разрулят).

**Frontend:**
- Экран подписки в Кабинете: список продуктов из StoreKit (локализованные цены), кнопка покупки, «Restore Purchases» (обязательно Apple), статус подписки.
- Убрать заглушку «Подписка скоро — в бете доступно всё» (`profile.upgradeNote`).
- Гейтинг фич уже работает через `entitlements` — просто `plan` теперь приходит от Apple.

**Acceptance:** в sandbox-аккаунте можно купить `ai`, фичи (микрофон/коуч) открываются; продление/отмена меняют `plan`; Restore работает.

### 5.5 Микрофон и аудио

**Микрофон:**
- `Info.plist`: `NSMicrophoneUsageDescription` (текст на языке витрины) — иначе reject.
- В WKWebView **нет** `webkitSpeechRecognition` → on-device-распознавание не работает; приложение использует ветку **MediaRecorder → server-STT** (она уже есть как fallback в `useRecorder.ts`). Нужно: убедиться, что `getUserMedia`+`MediaRecorder` работают в WKWebView (iOS 14.3+; контейнер будет `mp4/aac`, бэкенд STT это принимает — проверить).
- Если WKWebView-запись окажется нестабильной — заложить нативный плагин записи (`@capacitor-community/voice-recorder`) как план Б.
- **iOS 16+** как минимальный таргет: стабильные getUserMedia/MediaRecorder в WKWebView, StoreKit 2, актуальные API. (Можно обсудить 15.x — см. §11.)

**Аудио воспроизведение (сессии, мнемы):**
- Настроить `AVAudioSession` (категория `playback`) для корректной игры при беззвучном переключателе и (если нужно) в фоне.
- Проверить автоплей/жесты в WKWebView (`allowsInlineMediaPlayback`, `mediaTypesRequiringUserActionForPlayback = []`).

**Acceptance:** на реальном iPhone: запись голоса → скоринг работает; аудио сессий играет, в т.ч. при silent-switch.

### 5.6 Удаление аккаунта (требование Apple 5.1.1(v))

- Backend: `DELETE /api/auth/me` — удаляет пользователя и его данные (или анонимизирует), инвалидирует сессии.
- Frontend: в Кабинете «Удалить аккаунт» с подтверждением; после — logout.
- i18n-строки для всех 4 языков.

**Acceptance:** пользователь может удалить аккаунт из приложения; данные удаляются.

### 5.7 Приватность и согласия

- **Privacy Policy** (URL, обязательно) + **Terms/EULA**. Раскрыть передачу аудио/текста в OpenAI (под-процессор).
- **App Privacy «nutrition labels»** в App Store Connect: email (аккаунт), аудио/речь (для скоринга, уходит третьей стороне), usage data. Заполнить честно.
- Usage-description строки (микрофон; push — если будет).
- Возрастной рейтинг (вероятно 4+).
- Export compliance: используется стандартный HTTPS → exemption (`ITSAppUsesNonExemptEncryption=false`).

### 5.8 Нативная полировка

- **Иконка** (1024×1024 + наборы) и **splash screen** (бренд, бронза/`#F7F7F5`).
- **Статус-бар**: стиль под светлый фон; safe-area уже обрабатывается (`env(safe-area-inset-*)`) — проверить на устройствах с «островом».
- **Haptics** на свайп/флип карточки и на «Угадал/Не угадал» (`@capacitor/haptics`).
- Отключить overscroll/bounce там, где мешает; зафиксировать портрет.
- Проверить клавиатуру (inset) на экранах авторизации/импорта.

### 5.9 Push-уведомления (опционально, усиливает «не-webview»)

- APNs + `@capacitor/push-notifications`; бэкенд — токены устройств + отправка напоминаний о тренировке (ритм-ретеншн). Помогает и для ревью (нативная фича), и для retention. Можно во вторую волну.

### 5.10 Бэкенд-инфра

- Поддомен `api.executive-english.net` (Caddy, авто-TLS).
- CORS: добавить нативные origin (`capacitor://localhost`, `https://localhost`) и `api`-домен.
- Эндпоинты: `billing/verify`, `billing/apple-notifications`, `DELETE auth/me`, токен в login/register.
- Секреты: Apple shared secret / App Store Server API ключ (.p8), APNs ключ — в `.env`.
- Бэкап БД перед миграциями (как и раньше; новые поля `User` — аддитивная миграция в `_migrate`).

---

## 6. App Store Connect: подготовка и релиз

1. **Apple Developer Program** — $99/год (нужен аккаунт; см. §11/§12).
2. Bundle ID, App ID, сертификаты, provisioning (через Xcode «Automatically manage signing»).
3. Запись приложения в App Store Connect: название, подзаголовок, ключевые слова, описание (4 языка), категория (Education).
4. Подписки (IAP-продукты), их локализация и цены.
5. **Скриншоты**: 6.7" и 6.5" (актуальные требуемые размеры) — снять на симуляторе/устройстве, можно через наш `snapshot`-пайплайн адаптировать.
6. Privacy labels, privacy policy URL, age rating, export compliance.
7. **TestFlight**: внутреннее тестирование → внешнее (бета) → сабмит на ревью.
8. Демо-аккаунт для ревьюера (с доступом к платным фичам) — обязательно указать в Review Notes.

---

## 7. Риски ревью и митигации

| Риск (Guideline) | Митигация |
|---|---|
| **4.2 Minimum Functionality** (просто обёртка сайта) | Нативные IAP, микрофон-скоринг, (push), офлайн-кэш, haptics — это не «просто сайт». В Review Notes подчеркнуть нативные функции. |
| **3.1.1 IAP** (внешняя оплата) | Только Apple IAP в приложении; никаких ссылок на внешнюю оплату/Stripe внутри iOS-приложения. |
| **5.1.1(v) Account deletion** | Реализуем удаление аккаунта в приложении (§5.6). |
| **5.1.1 Sign in with Apple** | Требуется только если есть сторонний соц-логин (Google/FB). У нас email+пароль → **SiwA не обязателен.** (Если добавим соц-логин — придётся добавить SiwA.) |
| **Микрофон в WKWebView нестабилен** | План Б — нативный плагин записи (§5.5). Проверить рано, на Phase 1. |
| **Передача аудио в OpenAI** | Раскрыть в Privacy labels + policy; это допустимо при раскрытии. |
| **Пустой контент для ревьюера** | Демо-аккаунт с активированными бэтчами + платным планом. |

---

## 8. Этапы и вехи

**Phase 0 — Подготовка (1–2 дня).** Apple Developer аккаунт, bundle id, поддомен `api.`, решения из §11.

**Phase 1 — Нативный каркас + сеть + auth (3–5 дней).** Capacitor + iOS-проект; `API_BASE`; токен-авторизация (dual-mode); сборка на устройстве; первый билд в TestFlight (internal). *Контрольная точка: приложение логинится и работает на iPhone.*

**Phase 2 — IAP + удаление аккаунта + приватность (5–8 дней).** Продукты в ASC; покупка/Restore; серверная валидация + вебхук; даунгрейд по истечении; экран подписки; удаление аккаунта; privacy policy + labels. *Контрольная точка: sandbox-покупка `ai` открывает фичи.*

**Phase 3 — Микрофон/аудио + полировка (3–5 дней).** Проверка записи/STT и аудио на реальных устройствах (план Б при необходимости); иконка/splash/haptics/статус-бар; QA на нескольких iPhone (узкие/широкие/Zoom). 

**Phase 4 — Сабмит и ревью (3–7 дней календарных).** Скриншоты, метаданные, демо-аккаунт, внешний TestFlight, сабмит, ответы на замечания.

**Итого:** ~2 недели до рабочего TestFlight, ~4–5 недель до готовности к публикации (без учёта времени ревью Apple).

---

## 9. Состав работ по коду (что трогаем)

**Frontend:**
- `frontend/src/api.ts` — `API_BASE` + `apiUrl()` + `Authorization` header.
- `frontend/src/auth/AuthContext.tsx` — хранение/чтение токена (Preferences/Keychain).
- `frontend/src/main.tsx` — отключение SW в нативе; init Capacitor-плагинов.
- Кабинет (`Profile.tsx`) — экран подписки (продукты/Restore/статус), «Удалить аккаунт».
- i18n-локали — строки подписки/удаления/ошибок IAP (4 языка).
- Новые: `capacitor.config.ts`, нативный iOS-проект (`ios/`), хелпер `native.ts` (платформа, secure storage, haptics).

**Backend:**
- `routers/auth.py` — токен в login/register; `DELETE /me`; middleware Bearer-or-cookie.
- `routers/billing.py` (новый) — `verify`, `apple-notifications`.
- `models.py` — `User.plan_source/plan_expires_at/apple_original_tx_id` (+ аддитивная миграция в `db.py`).
- `main.py` — CORS под нативные origin; роутер billing.
- `entitlements.py` — без изменений (источник `plan` теперь Apple).

---

## 10. Критерии приёмки (Definition of Done)

- [ ] Приложение ставится из TestFlight на iPhone, проходит онбординг, работает на ru/es/de/fr.
- [ ] Логин/сессия сохраняются после перезапуска (токен в Keychain).
- [ ] Запись голоса → скоринг работает на реальном устройстве; аудио сессий играет.
- [ ] Покупка `core`/`ai` в sandbox открывает соответствующие фичи; Restore работает; истечение/отмена → даунгрейд.
- [ ] Удаление аккаунта из приложения работает.
- [ ] Privacy policy + App Privacy labels заполнены; usage-strings на месте.
- [ ] Иконка/splash/haptics/safe-area корректны на узких и широких iPhone.
- [ ] Веб-версия (`executive-english.net`) не сломана (cookie-auth жив).
- [ ] Прошёл App Review.

---

## 11. Решения, которые нужны от тебя

1. **Bundle ID / название в App Store**: `net.executiveenglish.app` ок? Имя «Executive English» (проверить занятость).
2. **Минимальная iOS**: 16+ (рекомендую) или 15+ (шире охват, чуть больше рисков с WKWebView-аудио)?
3. **IAP-реализация**: RevenueCat (быстрее) или нативный StoreKit 2 + наш сервер (без зависимостей)?
4. **Линейка подписок и цены**: какие планы платные (`core`, `ai`), периоды (мес/год), цены по рынкам, нужен ли триал/вводный оффер?
5. **Apple Developer аккаунт**: оформлен? На юр.лицо или ИП/физлицо? (нужно до Phase 4).
6. **Push сейчас или во вторую волну?**
7. **Privacy Policy / Terms**: есть готовые URL или нужно подготовить?

---

## 12. Аккаунты и затраты

- Apple Developer Program — **$99/год** (обязательно).
- RevenueCat — бесплатно до ~$2.5k MTR/мес, далее % (если выберем вариант A).
- OpenAI — текущие расходы на STT/скоринг/коуч (без изменений; растут с числом платных юзеров).
- Хостинг — текущий Hetzner (без изменений; добавляется поддомен).

---

---

## 13. Зафиксированные решения и ценообразование (2026-06-09)

**Решения (из ответов на §11):**
- IAP — **нативный StoreKit 2 + наш сервер** (вариант B), без RevenueCat.
- Минимальная **iOS 16+**.
- Apple Developer аккаунт — оформляет founder.
- Privacy Policy — готовим (черновик в составе работ).
- Триал — **не временной**, а freemium-лимит (см. ниже).
- Bundle id / push — push во вторую волну; bundle id `net.executiveenglish.app` (подтвердить при создании App ID).

**Ценообразование (по итогам рыночного research; цены — стандартные Apple price points):**

| План | Месяц | Год | Эфф. /мес (год) | Скидка год |
|---|---|---|---|---|
| **core** (библиотека + путь + практика + аудио, без AI-голоса) | **$12.99** | **$79.99** | ~$6.67 | ~49% |
| **ai** (core + микрофон + AI-скоринг + AI-коуч) — флагман | **$24.99** | **$149.99** | ~$12.50 | ~50% |

Обоснование: `core` стоит на уровне mainstream (Duolingo Super/Babbel/Busuu ~$70–90/год); `ai` — выше Speak/Loora ($84–120/год), но ниже потолка Duolingo Max ($168/год), что позиционирует продукт как «серьёзный executive-инструмент». Разрыв ×2 между годовыми тарифами чётко доносит, что AI — флагманская ценность. (Перед финалом сверить Speak и Loora напрямую в US App Store — цены промо-волатильны ±10–15%.) Опционально позже протестировать `ai`-год на $167.99.

**Freemium-модель (ФИНАЛ, реализовано):** не «3×3», а **один бэтч полностью бесплатный** (все фразы + микрофон/AI/коуч), **остальные — платные**. Человек проживает весь метод целиком, включая флагманский AI, на одной теме → потом платит за остальную библиотеку. Снимает риск «3 шагов мало» и даёт ощутить AI до пэйвола.
- На проде free-бэтч = #1 «Несогласие» (live-tone) — совпадает с примером онбординга (UNDERSTAND/WALK/READ/FAR). Меняется админ-эндпоинтом `POST /api/batches/{id}/free` (ровно один free-бэтч).
- `core` (платно): все бэтчи, без AI-голоса. `ai` (платно): все бэтчи + AI. Free-бэтч даёт AI всем.

---

## 14. Прогресс реализации

**Phase 1 — фундамент (готово, задеплоено, проверено 2026-06-09):**
- Авторизация **cookie-или-Bearer** (бэкенд `main.py` auth-gate + `_serialize` отдаёт `token`); веб не тронут (cookie 200), нативный путь (Bearer 200), no-auth 401, CORS preflight с `capacitor://localhost` → 200. Проверено curl'ом на локальном бэкенде.
- Фронтенд: `lib/session.ts` (токен в Keychain через `@capacitor/preferences`, на вебе — no-op), `API_BASE` + `apiFetch()` + `mediaUrl()` в `api.ts`, `AuthContext` грузит/хранит/чистит токен, SW отключён в нативе, `capacitor.config.ts`.
- Capacitor (`@capacitor/core` + cli + preferences) поставлен. `npx cap add ios` — после Apple-аккаунта/Xcode.

**Phase 1.5 — freemium-гейт (готово, задеплоено, проверено e2e 2026-06-17):**
- `Batch.is_free` (+ миграция) · `app/access.py` (`batch_usable`, `ai_on_batch`) · гейтинг в эндпоинтах: дека (фильтр + per-card `ai_allowed`), voice answer/answer-text/coach (AI per-batch), создание сессии, активация бэтча, list/detail (`locked`/`is_free`, контент платных бэтчей не отдаётся) · админ-эндпоинт `POST /api/batches/{id}/free`.
- Фронт: `DeckCard.ai_allowed` + `canVoice` per-card (free-бэтч даёт микрофон free-юзеру), пэйвол в `BatchHome` для locked-бэтчей (i18n ru/es/de/fr), типы `locked`/`is_free`.
- E2E проверено: free-юзер видит только free-бэтч в деке/уроках с активным AI; платные → locked (403 на активацию/сессию, контент скрыт); ai-юзер → всё. На проде free-бэтч = #1.

**§5.6 Удаление аккаунта (готово, задеплоено, проверено 2026-06-17):** `DELETE /api/auth/me` сносит per-user state/события + приватные импорты юзера (+ их контент) + сам аккаунт; чистит cookie/токен. Кабинет: «Удалить аккаунт» с two-tap подтверждением (i18n ru/es/de/fr). E2E: токен умирает, повторный логин 401, данные стёрты.

**Тулчейн на Mac founder (проверено 2026-06-17):** Node ✅; **нет Xcode** (только CLT), **нет CocoaPods**, нет Homebrew (Ruby 2.6 системный). Поставить: Xcode (App Store) + Homebrew + `brew install cocoapods`. Apple Developer аккаунт — для девайса/TestFlight/IAP-sandbox. Симулятор: микрофон НЕ работает (голос тестим на реальном айфоне).

**§5.5 native media-auth (готово, задеплоено, проверено 2026-06-17):** `/covers` и `/audio` выведены из auth-gate → публичные (файлы — неперечислимые хэши; какие URL ты получаешь, решает API за пэйволом). Фронт: `mediaUrl()` подставляет абсолютный base на нативе — обёрнуты `BatchCover` (обложки) и 4 audio-метода API. Проверено: `/covers|/audio` unauth → 404 (не 401), `/api` → 401, реальная обложка unauth → 200.

**§5.4 IAP — серверный фундамент (готово, задеплоено, проверено 2026-06-17):** поля `User.plan_source/plan_expires_at/apple_original_tx_id` (+ миграция); `effective_plan(u)` — истёкшая подписка → free (вшито в `/me` + `user_entitlements`); модуль `app/routers/billing.py`: `PRODUCT_PLAN` (core/ai × monthly/yearly), `_apply_purchase`, `POST /api/billing/verify` (authed) и `POST /api/billing/apple-notifications` (public webhook). Проверено e2e: миграция, expiry (past→free / future→ai), verify→501 (инертен, без дыры), webhook→200, verify-unauth→401.
- ⚠️ **Подпись StoreKit-2 JWS (`_verify_signed_jws`) — заглушка** (возвращает False → `/verify` отдаёт 501, плана не выдаёт). Реализуется + валидируется в sandbox, когда будет Apple Developer аккаунт (нужен Apple Root CA G3 + `pyjwt[crypto]`). Без неё дыры нет — просто инертно.

**Нативная сборка (готово, проверено на симуляторе 2026-06-17):** тулчейн установлен (Xcode 26.5, Homebrew 6.0.2, CocoaPods 1.16.2). `@capacitor/ios` + `npx cap add ios` → нативный проект `frontend/ios/` (CocoaPods locale-баг обойдён через `LANG/LC_ALL=en_US.UTF-8`). Собрал через `xcodebuild` (simulator, без подписи), установил и запустил на **iPhone 17 Pro** — приложение грузит наш UI из бандла, рендерит экран входа (i18n RU), переключатель 🌐 на месте. Поправил safe-area для `.auth-topbar` (был под Dynamic Island). `ios/.gitignore` исключает Pods/build/public. Podfile `platform :ios` пока 13.0 — поднять до 16 при полировке.

**Команда сборки (для повтора):** `cd frontend && npm run build && (export PATH="/opt/homebrew/bin:$PATH" LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 && npx cap sync ios && cd ios/App && xcodebuild -workspace App.xcworkspace -scheme App -sdk iphonesimulator -destination "id=<UDID>" -derivedDataPath build CODE_SIGNING_ALLOWED=NO build)` → `xcrun simctl install/launch/io ... screenshot`.

**Дальше:** `npx cap add ios` → реальная сборка на симуляторе · реализация `_verify_signed_jws` + sandbox-тест IAP · экран подписки в кабинете (StoreKit-плагин) · device-тест микрофона · иконка/splash/haptics · lock-бейджи на карточках (полировка) · TestFlight. · §5.6 удаление аккаунта · §5.5 нативный media-auth (cover/audio на нативе через img/audio не несут Bearer — решить: публичные covers или token-в-query) · экран подписки в кабинете · lock-бейджи на карточках Библиотеки (полировка) · `npx cap add ios` + иконка/splash/haptics.

