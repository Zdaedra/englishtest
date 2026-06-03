// The learner profile, captured once by onboarding. Single user, so localStorage
// is the source of truth. One question only — which real-world tasks the learner
// needs English for — and those chosen scenarios shape the whole trajectory
// (which sections lead the path). No level test: difficulty adapts on its own.

import type { Strategy } from "./strategy";
import { DEFAULT_STRATEGY } from "./strategy";

export type UserProfile = {
  scenarios?: string[]; // SCENARIOS keys, 1-2 chosen (legacy seed for strategy)
  strategy?: Strategy; // the adaptive focus route (source of truth once tuned)
  onboardedAt?: string; // ISO; presence = onboarding done
};

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

// The active strategy: an explicitly tuned one wins; otherwise derive it from the
// onboarding picks (SCENARIOS keys are focus keys); otherwise the default.
export function getStrategy(): Strategy {
  const p = getProfile();
  if (p.strategy?.main) return { ...DEFAULT_STRATEGY, ...p.strategy };
  const picks = (p.scenarios ?? []).filter(Boolean);
  if (picks.length)
    return { ...DEFAULT_STRATEGY, main: picks[0], secondary: picks.slice(1, 3) };
  return DEFAULT_STRATEGY;
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
