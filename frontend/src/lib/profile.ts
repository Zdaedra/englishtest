// The learner profile, captured once by onboarding. Single user, so localStorage
// is the source of truth. One question only — which real-world tasks the learner
// needs English for — and those chosen scenarios shape the whole trajectory
// (which sections lead the path). No level test: difficulty adapts on its own.

import type { Strategy } from "./strategy";
import { DEFAULT_STRATEGY, leagueAdjust } from "./strategy";
import { getLeagueResult } from "./league";

export type UserProfile = {
  scenarios?: string[]; // SCENARIOS keys, 1-2 chosen (legacy seed for strategy)
  strategy?: Strategy; // the adaptive focus route (source of truth once tuned)
  onboardedAt?: string; // ISO; presence = onboarding done
  // C1: who assembles the plan. "auto" = the strategy weaves all batches;
  // "manual" = the learner's own hand-picked set (manualIds, in pick order).
  // Switching modes ARCHIVES, never erases: both the strategy and the manual
  // set stay in the profile, and batch progress lives per-batch on the server,
  // so it is absolute across any number of switches.
  planMode?: PlanMode;
  manualIds?: number[];
};

export type PlanMode = "auto" | "manual";

// Each goal boosts a set of sections to the front of the path. The 7 presence
// directions are the core product (each maps to its own section); "Деловая
// коммуникация" boosts the business-эталон domains.
export const SCENARIOS: { key: string; label: string; sections: string[] }[] = [
  { key: "charisma", label: "Харизма и обаяние", sections: ["charisma"] },
  { key: "flirt", label: "Флирт и притяжение", sections: ["flirt"] },
  { key: "intimacy", label: "Близость и отношения", sections: ["intimacy"] },
  { key: "lead-presence", label: "Лидерство без должности", sections: ["lead-presence"] },
  { key: "composure", label: "Самообладание и достоинство", sections: ["composure"] },
  { key: "gravitas", label: "Вес в кризисе", sections: ["gravitas"] },
  { key: "stage", label: "Сцена и публичность", sections: ["stage"] },
  {
    key: "business",
    label: "Деловая коммуникация",
    sections: ["live-tone", "pitch", "negotiation", "pressure", "repair", "leadership", "requests"],
  },
];

const KEY = "ee-profile";

export function getProfile(): UserProfile {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}");
  } catch {
    return {};
  }
}

export function setProfile(patch: Partial<UserProfile>): UserProfile {
  const next = { ...getProfile(), ...patch };
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage disabled — profile is non-critical */
  }
  return next;
}

export function isOnboarded(): boolean {
  return !!getProfile().onboardedAt;
}

// Lightweight day-streak: call once when the home screen opens. Same day → no
// change; consecutive day → +1; a gap → reset to 1. Stored in localStorage.
const STREAK_KEY = "ee-streak";
export function recordVisit(): number {
  const today = new Date();
  const dayStr = `${today.getFullYear()}-${today.getMonth() + 1}-${today.getDate()}`;
  let data: { last?: string; count?: number } = {};
  try {
    data = JSON.parse(localStorage.getItem(STREAK_KEY) || "{}");
  } catch {
    /* ignore */
  }
  if (data.last === dayStr) return data.count || 1;
  const y = new Date(today);
  y.setDate(y.getDate() - 1);
  const yStr = `${y.getFullYear()}-${y.getMonth() + 1}-${y.getDate()}`;
  const count = data.last === yStr ? (data.count || 0) + 1 : 1;
  try {
    localStorage.setItem(STREAK_KEY, JSON.stringify({ last: dayStr, count }));
  } catch {
    /* ignore */
  }
  return count;
}

// The active strategy: an explicitly tuned one wins; otherwise derive it from the
// onboarding picks (SCENARIOS keys are focus keys); otherwise the default. Until
// the learner tunes the path themselves, the league placement (if taken) sets the
// starting intensity + sprint size — the test result shapes the programme (B2).
export function getStrategy(): Strategy {
  const p = getProfile();
  if (p.strategy?.main) return { ...DEFAULT_STRATEGY, ...p.strategy };
  const league = getLeagueResult();
  const pace = league ? leagueAdjust(league.tier) : {};
  const picks = (p.scenarios ?? []).filter(Boolean);
  if (picks.length)
    return { ...DEFAULT_STRATEGY, ...pace, main: picks[0], secondary: picks.slice(1, 4) };
  return { ...DEFAULT_STRATEGY, ...pace };
}

// True while the sprint pace comes from the league result (nothing hand-tuned yet)
// — lets Tune-your-path label WHY the defaults look the way they do.
export function paceFromLeague(): boolean {
  const p = getProfile();
  return !p.strategy?.main && !!getLeagueResult();
}

// ── C1: manual plan mode ─────────────────────────────────────────────────────
// The same event the batch menu dispatches — every plan surface already
// re-renders on it (useProgressVersion), so mode/set changes repaint the map.
function notifyPlanChanged(): void {
  try { window.dispatchEvent(new Event("ee-progress-changed")); } catch { /* ssr */ }
}

export function getPlanMode(): PlanMode {
  return getProfile().planMode === "manual" ? "manual" : "auto";
}

export function setPlanMode(mode: PlanMode): void {
  setProfile({ planMode: mode });
  notifyPlanChanged();
}

export function manualIds(): number[] {
  return (getProfile().manualIds ?? []).filter((x) => typeof x === "number");
}

export function isInManual(id: number): boolean {
  return manualIds().includes(id);
}

// Adding a batch by hand IS the intent to drive the plan yourself — the mode
// flips to manual right away (the auto plan stays archived in the strategy).
export function addManual(id: number): void {
  const ids = manualIds();
  if (!ids.includes(id)) ids.push(id);
  setProfile({ manualIds: ids, planMode: "manual" });
  notifyPlanChanged();
}

export function removeManual(id: number): void {
  setProfile({ manualIds: manualIds().filter((x) => x !== id) });
  notifyPlanChanged();
}

export function setStrategy(s: Strategy): void {
  setProfile({ strategy: s });
}

// Section slugs ranked by the chosen scenarios first (in their natural order),
// then everything else. Used to order the path's chapters per the learner's goal.
export function prioritySectionSlugs(p: UserProfile, natural: string[]): string[] {
  const wanted = new Set<string>();
  for (const key of p.scenarios ?? []) {
    const sc = SCENARIOS.find((s) => s.key === key);
    sc?.sections.forEach((slug) => wanted.add(slug));
  }
  const lead = natural.filter((slug) => wanted.has(slug));
  const rest = natural.filter((slug) => !wanted.has(slug));
  return [...lead, ...rest];
}
