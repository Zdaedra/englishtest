// The adaptive focus route (consilium design: Opus 4.8 + GPT-5).
// Instead of one linear snake of all 89 batches, the learner has a small "current
// sprint" weighted by their chosen focus. They can re-tune it any time and the
// sprint rebuilds live; per-batch progress is preserved (SRS lives separately).

import { BatchListItem } from "../api";
import { orderedSections } from "./sections";
import { tg } from "../i18n";

export type Intensity = "narrow" | "balanced" | "explore";

export type Strategy = {
  main: string; // focus key (a presence section slug, or "business")
  secondary: string[]; // 0–2 focus keys
  intensity: Intensity;
  sprintSize: number; // 3 | 5 | 7
  need?: string; // optional "current need" key (one-tap situation)
};

// The 8 focus units shown in onboarding / Tune-your-path: 7 presence directions
// (each = one section) + the business-эталон group.
export const FOCUSES: { key: string; ru: string }[] = [
  { key: "charisma", ru: "Харизма" },
  { key: "flirt", ru: "Флирт" },
  { key: "intimacy", ru: "Близость" },
  { key: "lead-presence", ru: "Лидерство" },
  { key: "composure", ru: "Самообладание" },
  { key: "gravitas", ru: "Гравитас" },
  { key: "stage", ru: "Сцена" },
  { key: "business", ru: "Бизнес" },
];
export const FOCUS_RU: Record<string, string> = Object.fromEntries(
  FOCUSES.map((f) => [f.key, f.ru])
);

// One-tap "what's on you this week" — each nudges a direction to the front.
export const NEEDS: { key: string; label: string; focus: string }[] = [
  { key: "presentation", label: "У меня выступление", focus: "stage" },
  { key: "hard-talk", label: "Трудный разговор", focus: "intimacy" },
  { key: "authority", label: "Нужен вес / авторитет", focus: "gravitas" },
  { key: "charisma", label: "Хочу больше харизмы", focus: "charisma" },
  { key: "pressure", label: "Я под давлением", focus: "composure" },
];

const BUSINESS_SECTIONS = [
  "live-tone", "pitch", "negotiation", "pressure",
  "repair", "leadership", "requests", "written", "small-talk",
];

export const DEFAULT_STRATEGY: Strategy = {
  main: "charisma", secondary: [], intensity: "balanced", sprintSize: 5,
};

const numOf = (slug: string) => {
  const m = slug.match(/(\d+)\s*$/);
  return m ? parseInt(m[1], 10) : 0;
};

// Which section slugs a focus key covers.
export function sectionsFor(focus: string): string[] {
  return focus === "business" ? BUSINESS_SECTIONS : [focus];
}

// Display weight mix (main / secondary / business / discovery), per the consilium.
export function weightMix(s: Strategy): { label: string; pct: number }[] {
  const hasSec = s.secondary.length > 0;
  const main = tg(`focus.${s.main}`);
  const sec = hasSec ? s.secondary.map((k) => tg(`focus.${k}`)).join(" / ") : "";
  if (s.intensity === "narrow")
    return [
      { label: main, pct: 75 },
      ...(hasSec ? [{ label: sec, pct: 15 }] : [{ label: tg("focus.business"), pct: 15 }]),
      { label: tg("mix.discovery"), pct: 10 },
    ];
  if (s.intensity === "explore")
    return [
      { label: main, pct: 40 },
      ...(hasSec ? [{ label: sec, pct: 20 }] : []),
      { label: tg("focus.business"), pct: 20 },
      { label: tg("mix.discovery"), pct: hasSec ? 20 : 40 },
    ];
  // balanced
  return hasSec
    ? [
        { label: main, pct: 50 },
        { label: sec, pct: 25 },
        { label: tg("focus.business"), pct: 15 },
        { label: tg("mix.discovery"), pct: 10 },
      ]
    : [
        { label: main, pct: 60 },
        { label: tg("focus.business"), pct: 15 },
        { label: tg("mix.discovery"), pct: 25 },
      ];
}

type Alloc = { main: number; sec: number; bridge: number; disc: number };
function alloc(s: Strategy): Alloc {
  const N = s.sprintSize;
  const hasSec = s.secondary.length > 0;
  if (s.intensity === "narrow") {
    const main = Math.max(1, N - 1);
    return { main, sec: 0, bridge: N - main, disc: 0 };
  }
  if (s.intensity === "explore") {
    const main = Math.max(1, Math.round(N * 0.4));
    const sec = hasSec ? 1 : 0;
    const bridge = 1;
    return { main, sec, bridge, disc: Math.max(0, N - main - sec - bridge) };
  }
  // balanced
  const main = Math.max(1, Math.round(N * 0.6));
  const sec = hasSec ? 1 : 0;
  const bridge = 1;
  return { main, sec, bridge, disc: Math.max(0, N - main - sec - bridge) };
}

// Build the current sprint: an ordered list of batches weighted by the strategy,
// always preferring not-yet-closed batches. Falls back to filling from the global
// incomplete priority order so the sprint is always full when material remains.
export function buildSprint(
  s: Strategy,
  batches: BatchListItem[],
  isClosed: (id: number) => boolean
): BatchListItem[] {
  const incompleteBySection = new Map<string, BatchListItem[]>();
  for (const b of batches) {
    if (!b.section || isClosed(b.id)) continue;
    const arr = incompleteBySection.get(b.section) ?? [];
    arr.push(b);
    incompleteBySection.set(b.section, arr);
  }
  for (const arr of incompleteBySection.values())
    arr.sort((a, b) => numOf(a.slug) - numOf(b.slug));

  const used = new Set<number>();
  const out: BatchListItem[] = [];
  const take = (focusKeys: string[], count: number) => {
    let n = count;
    for (const fk of focusKeys) {
      for (const sec of sectionsFor(fk)) {
        for (const b of incompleteBySection.get(sec) ?? []) {
          if (n <= 0) return;
          if (used.has(b.id)) continue;
          used.add(b.id);
          out.push(b);
          n--;
        }
      }
    }
  };

  const a = alloc(s);
  take([s.main], a.main);
  if (a.sec) take(s.secondary, a.sec);
  if (a.bridge) take(["business"], a.bridge);
  if (a.disc) {
    const others = orderedSections()
      .map((x) => x.slug)
      .filter(
        (slug) =>
          !sectionsFor(s.main).includes(slug) &&
          !s.secondary.some((k) => sectionsFor(k).includes(slug)) &&
          !BUSINESS_SECTIONS.includes(slug)
      );
    take(others, a.disc);
  }

  // Fill any shortfall from the global incomplete list in priority order.
  if (out.length < s.sprintSize) {
    const priority = orderedSections().map((x) => x.slug);
    for (const slug of priority) {
      for (const b of incompleteBySection.get(slug) ?? []) {
        if (out.length >= s.sprintSize) break;
        if (used.has(b.id)) continue;
        used.add(b.id);
        out.push(b);
      }
    }
  }
  return out.slice(0, s.sprintSize);
}
