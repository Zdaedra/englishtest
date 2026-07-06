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

// League → programme intensity (B2: the placement result must DO something).
// functional = narrow focus + short sprints (denser repetition of fewer batches);
// native = wider field + longer sprints (repertoire growth, not survival drills).
// Applied as the DEFAULT until the learner explicitly tunes their path, and
// offered as a one-tap re-tune on the league result screen.
export function leagueAdjust(tier: string): Pick<Strategy, "intensity" | "sprintSize"> {
  switch (tier) {
    case "functional": return { intensity: "narrow", sprintSize: 3 };
    case "confident": return { intensity: "balanced", sprintSize: 5 };
    case "sharp": return { intensity: "balanced", sprintSize: 7 };
    case "native": return { intensity: "explore", sprintSize: 7 };
    default: return { intensity: "balanced", sprintSize: 5 };
  }
}

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

// Focus buckets — like weightMix, but each row also carries the focus KEY and the
// set of section slugs it covers, so the Learning screen can join allocation
// (intent) with real per-domain competence (fact) in one row. Same percentages as
// weightMix; the extra fields let "Твои домены" show fill = competence, marker = focus.
export type FocusBucket = { key: string; label: string; pct: number; sections: string[] };
export function focusBuckets(s: Strategy): FocusBucket[] {
  const hasSec = s.secondary.length > 0;
  const others = orderedSections()
    .map((x) => x.slug)
    .filter(
      (slug) =>
        !sectionsFor(s.main).includes(slug) &&
        !s.secondary.some((k) => sectionsFor(k).includes(slug)) &&
        !BUSINESS_SECTIONS.includes(slug)
    );
  const main: FocusBucket = { key: s.main, label: tg(`focus.${s.main}`), pct: 0, sections: sectionsFor(s.main) };
  const sec: FocusBucket = { key: "secondary", label: s.secondary.map((k) => tg(`focus.${k}`)).join(" / "), pct: 0, sections: s.secondary.flatMap(sectionsFor) };
  const biz: FocusBucket = { key: "business", label: tg("focus.business"), pct: 0, sections: BUSINESS_SECTIONS };
  const disc: FocusBucket = { key: "discovery", label: tg("mix.discovery"), pct: 0, sections: others };
  const at = (b: FocusBucket, pct: number) => ({ ...b, pct });
  if (s.intensity === "narrow")
    return hasSec
      ? [at(main, 75), at(sec, 15), at(disc, 10)]
      : [at(main, 75), at(biz, 15), at(disc, 10)];
  if (s.intensity === "explore")
    return hasSec
      ? [at(main, 40), at(sec, 20), at(biz, 20), at(disc, 20)]
      : [at(main, 40), at(biz, 20), at(disc, 40)];
  // balanced
  return hasSec
    ? [at(main, 50), at(sec, 25), at(biz, 15), at(disc, 10)]
    : [at(main, 60), at(biz, 15), at(disc, 25)];
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

// ─────────────────────────────────────────────────────────────────────────────
// Domain-apportioned trajectory (the whole learning plan, not one sprint).
//
// THE PROBLEM this solves: grouping the map by section produced "all Charisma,
// then all Flirt, then …" — the focus mix the learner configured was invisible.
// Instead the whole field is woven into one ordered plan and chunked into
// fixed-size SPRINTS, so inside every sprint the domains appear in proportion to
// their focus %. A domain that can't fit its share early simply spills later.
//
// THE MATH — sequential highest-averages (Sainte-Laguë). We build the order one
// batch at a time. At each step we take from the domain with the highest priority
//     pᵈ = weightᵈ / (2·placedᵈ + 1)
// among domains that still have batches. This is the apportionment rule that
// spreads a LOW-weight domain EVENLY across the plan instead of starving it: a
// 10%-weight domain surfaces ~once per two 5-slot sprints, rather than rounding
// to zero every sprint and dumping at the very end (the failure of a memoryless
// per-sprint round). When a high-weight domain runs dry its share flows to the
// rest, so its surplus batches naturally land in later sprints — the carry-over
// the design calls for. Verified across configs in the math harness.
// ─────────────────────────────────────────────────────────────────────────────

export type Sprint = { items: BatchListItem[] };
export type Trajectory = {
  order: BatchListItem[]; // the full plan, flattened (sprint 1 then sprint 2 …)
  sprints: Sprint[]; // `order` chunked into sprints of `sprintSize`
  domainOf: Map<number, string>; // batchId → focus-bucket key (for per-sprint mix)
};

// Build the full domain-apportioned trajectory. `sectionPriority` is the
// learner's section order (scenarios first) — passed in to keep this module free
// of a profile import (profile.ts already depends on strategy.ts).
export function buildTrajectory(
  s: Strategy,
  batches: BatchListItem[],
  sectionPriority: string[]
): Trajectory {
  const buckets = focusBuckets(s);
  // Clamp: the UI offers 3/5/7, but a corrupt profile must not produce a
  // 999-batch sprint (breaks the map's road measurement).
  const S = Math.min(12, Math.max(1, s.sprintSize || 5));
  const fallbackKey =
    buckets.find((b) => b.key === "discovery")?.key ??
    buckets[buckets.length - 1]?.key ??
    "discovery";

  // section slug → bucket key (every section resolves to exactly one bucket;
  // anything a focus config drops is swept into the fallback so nothing strands).
  const secToBucket = new Map<string, string>();
  for (const bk of buckets) for (const sec of bk.sections) secToBucket.set(sec, bk.key);

  const secRank = new Map(sectionPriority.map((slug, i) => [slug, i] as const));
  const queues = new Map<string, BatchListItem[]>(buckets.map((b) => [b.key, []]));
  for (const b of batches) {
    if (!b.section) continue;
    const key = secToBucket.get(b.section) ?? fallbackKey;
    (queues.get(key) ?? queues.set(key, []).get(key)!).push(b);
  }
  for (const arr of queues.values())
    arr.sort(
      (a, b) =>
        (secRank.get(a.section!) ?? 1e9) - (secRank.get(b.section!) ?? 1e9) ||
        numOf(a.slug) - numOf(b.slug)
    );

  const domainOf = new Map<number, string>();
  for (const [key, arr] of queues) for (const b of arr) domainOf.set(b.id, key);

  // Walk the plan one batch at a time by Sainte-Laguë priority. The cursor per
  // domain advances through its (already section-ordered) queue.
  const cursor = new Map<string, number>(buckets.map((b) => [b.key, 0]));
  let total = 0;
  for (const arr of queues.values()) total += arr.length;
  const order: BatchListItem[] = [];
  while (order.length < total) {
    let best: FocusBucket | null = null;
    let bestVal = -1;
    for (const bk of buckets) {
      const q = queues.get(bk.key)!;
      const c = cursor.get(bk.key)!;
      if (c >= q.length) continue; // depleted
      // placed so far for this domain = cursor; +1e-9 keeps ties left-to-right
      // (buckets are main, secondary, business, discovery — the focus order).
      const val = bk.pct / (2 * c + 1);
      if (val > bestVal + 1e-9) { bestVal = val; best = bk; }
    }
    if (!best) break; // safety: nothing left to place
    const c = cursor.get(best.key)!;
    order.push(queues.get(best.key)![c]);
    cursor.set(best.key, c + 1);
  }

  const sprints: Sprint[] = [];
  for (let i = 0; i < order.length; i += S) sprints.push({ items: order.slice(i, i + S) });
  return { order, sprints, domainOf };
}

// C1: the manual plan — the learner's hand-picked batches, in pick order,
// chunked into the same sprints. domainOf still resolves through the focus
// buckets so "Твои домены" and the per-sprint mix keep working unchanged.
export function buildManualTrajectory(
  ids: number[],
  s: Strategy,
  batches: BatchListItem[]
): Trajectory {
  const S = Math.min(12, Math.max(1, s.sprintSize || 5));
  const byId = new Map(batches.map((b) => [b.id, b] as const));
  const order = ids.map((id) => byId.get(id)).filter(Boolean) as BatchListItem[];

  const buckets = focusBuckets(s);
  const fallbackKey = buckets[buckets.length - 1]?.key ?? "discovery";
  const secToBucket = new Map<string, string>();
  for (const bk of buckets) for (const sec of bk.sections) secToBucket.set(sec, bk.key);
  const domainOf = new Map<number, string>();
  for (const b of order) domainOf.set(b.id, secToBucket.get(b.section ?? "") ?? fallbackKey);

  const sprints: Sprint[] = [];
  for (let i = 0; i < order.length; i += S) sprints.push({ items: order.slice(i, i + S) });
  return { order, sprints, domainOf };
}
