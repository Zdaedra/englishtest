# Executive English — Design Language (v1)

> **For AI tools & devs.** When designing or coding any new screen/component, follow
> this. Visual reference (rendered): **`frontend/public/design-system.html`**
> (live at `https://executive-english.net/design-system.html`). All tokens below
> mirror the real source of truth, **`frontend/src/index.css`** (`:root`).

## Feel
Apple Music / Apple Fitness+ premium — but about **speech, memory, language**, not
music. Calm, airy, premium. **One brand accent: green.** No gamification (no points,
streaks, lives, reward badges). Content is the hero; the UI just supports movement.
The user should feel they're starting a *prepared training*, not filling a web form.

## Colour (use CSS vars, don't hardcode)
| Token | Value | Use |
|---|---|---|
| `--map-green` | `#1C8C63` | **the** accent: active state, icons, links |
| `--map-green-ink` | `#15714F` | text on green-soft |
| green light | `#34B07E` / CTA top `#27AB7B` | CTA gradient |
| `--map-green-soft` | `rgba(28,140,99,.14)` | tint chips/circles/badges |
| `--text` | `#111111` | primary text |
| `--muted` | `#6B6B6B` | secondary text |
| `--faint` | `#9A9A9A` | captions, dashed lines |
| inactive | `#8E8E93` | inactive tab/label |
| `--card` | `#FFFFFF` | cards |
| soft bg | `linear-gradient(180deg,#FCFCFC,#F4F7F4)` | premium screen background |
| `--mark` | `#9A7B4F` | bronze — rare legacy text accent only |
| `--danger` | `#C0564B` | **errors only** |

**Never** use blue / purple / red as an accent. Green only. Danger red only for real errors.

## Typography (SF Pro Display headings, Text for UI)
- Display `40 / 820 / -.02em` (screen title, e.g. "Тесты")
- Title `34 / 820 / -.02em` (batch title)
- Heading `22 / 760`
- Body `18 / line-height 1.5`
- UI `15 / 600`
- Caption `12 / 750 / .08em / UPPERCASE` — usually in `--map-green`

## Shape & elevation
- Radii: `12` chips · `18–20` cards · `24` cover/CTA · `28` hero card · `999` pill/circle.
- Shadows are **soft, low-contrast, diffuse** (premium paper, not material):
  - card `0 8px 26px rgba(17,17,17,.06), 0 1px 3px rgba(17,17,17,.04)`
  - hero `0 16px 44px rgba(17,17,17,.14)`
- More important = bigger radius + more lift.

## Motion (one spring; calm; no bounce/flash)
- Spring: `cubic-bezier(.22,1,.36,1)` (`--spring`) — base for all transitions.
- Press: `scale(.97)` ~150ms on CTAs/cards.
- Lens-pop: icon `1 → 1.5 → rest` 440ms back-out (`cubic-bezier(.34,1.56,.64,1)`) via Web Animations API on tap.
- Pill travel: `transform .6s` spring (nav active lens between tabs).
- Gel: `scaleX 1.16 / scaleY .9 → 1` (liquid deform on tab change).
- Glow: green CTA breathes ~3.4s ease-in-out.
- Screen enter: fade + slide-up ~8–10px.

## Component recipes
- **Primary CTA** `.l3-cta`: 64px, radius 24, `linear-gradient(135deg,#27AB7B,#1C8C63)`,
  shadow `0 14px 30px -10px rgba(28,140,99,.55)` + inset top highlight, breathing glow,
  icon + label white 18/640. **One per screen.**
- **Back/secondary** = white pill (`999`) or 44×44 white circle, soft shadow, green chevron.
- **Tag pill** = green-soft bg, `--map-green-ink`, 12px UPPERCASE (e.g. "УРОК 3").
- **Content card** = white, radius 20–28, soft card shadow. **Active** = green-tint bg
  (`linear-gradient(180deg,#F1FAF5,#fff)`) + `rgba(28,140,99,.28)` border + green title.
  **Done** = green-filled circle with check. **Locked** = `opacity:.6`.
- **Number/step circle** = 40–44px; idle green-soft + green-ink; active filled green + white
  (+ optional play badge); done green-soft + check; future outline gray.
- **Warning** = white card (radius 18) + shield/mic icon in green-soft circle + chevron;
  highlighted words (Safari/Chrome) in green. **Never** a bare red error line.
- **Anchor chain** = white card, `display:flex;flex-wrap:wrap;gap:7px 9px`; bold dark
  anchors with green `→` between (arrows may start a wrapped line).
- **Decorative voice-wave** = low-opacity green gradient bars at a card foot (speech motif).
- **Hint** = centered tiny `--faint` text with headphones icon.

## Floating glass navigation (the only glassmorphism)
- Two detached floating elements: **capsule** (3 tabs) + **separate** round search button.
- Capsule 56px, radius 28, `rgba(255,255,255,.58)` + `backdrop-filter: saturate(190%) blur(26px)`.
- Active = one **liquid-glass pill** (translucent gloss gradient `.8→.4` + `blur(14) saturate(210) brightness(1.06)`,
  1px white border, inner top highlight + faint cool/warm chromatic side edges). Slides with spring + gel;
  **drag along the bar to move selection** (pointer drag → lens follows finger).
- Active icon = `--map-green`, magnified `scale(1.18)`; inactive `#8E8E93`. Tap → lens-pop.
- ⚠️ **iOS limit:** true backdrop *refraction* (Apple Liquid Glass) is impossible on web —
  Safari doesn't support SVG `feDisplacementMap` in `backdrop-filter` (WebKit #245510). We ship the
  translucency + gloss + chromatic-rim + lens motion approximation. Real refraction = native app only.

## Illustration & icons
- Hero illustrations: **Apple-style matte-plastic 3D**, translucent green, soft baked shadow,
  transparent PNG. Theme = speech/memory (speech bubble, pencil, microphone). Generate with
  `gpt-image-1` (`background:transparent, quality:high`), then crop+resize to ~480px / ~160 KB,
  store in `frontend/public/art/…`. Example: `/art/lesson3-hero.png`.
- UI icons: thin stroke `1.7`, round caps, 24px grid, `currentColor`. Active green, inactive `#8E8E93`.

## Do / Don't
**Do:** lots of air + big top title · one green accent · white soft cards with diffuse shadows ·
glass only in the bottom nav · calm checkmarks/percentages for progress · matte green 3D art.
**Don't:** red/blue/purple accents · heavy black buttons / hard shadows · gamification ·
glass on content cards · bouncy/flashy transitions · cramped grids / web-form feel.

---
*Keep this in sync with `frontend/src/index.css`. Page-scoped class prefixes today:
`.l3-*` (Lesson 3 "Тесты"), `.bh-*` (batch overview), `.nav-*` (floating dock).*
