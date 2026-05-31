// The learner profile, captured once by onboarding. Single user, so localStorage
// is the source of truth. One question only — which real-world tasks the learner
// needs English for — and those chosen scenarios shape the whole trajectory
// (which sections lead the path). No level test: difficulty adapts on its own.

export type UserProfile = {
  scenarios?: string[]; // SCENARIOS keys, 1-2 chosen
  onboardedAt?: string; // ISO; presence = onboarding done
};

// Each real-world scenario boosts a set of the 9 sections to the front of the path.
export const SCENARIOS: { key: string; label: string; sections: string[] }[] = [
  { key: "negotiation", label: "Переговоры", sections: ["negotiation", "pressure"] },
  { key: "presentation", label: "Презентации", sections: ["pitch", "leadership"] },
  { key: "calls", label: "Звонки и созвоны", sections: ["small-talk", "requests", "live-tone"] },
  { key: "writing", label: "Письма и сообщения", sections: ["written", "requests"] },
  { key: "networking", label: "Нетворкинг", sections: ["small-talk", "live-tone"] },
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
