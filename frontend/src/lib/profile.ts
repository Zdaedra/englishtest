// The learner profile — goals, strategy, plan mode, manual set, league result.
// ACCOUNT-level state: the server (`User.learn_profile`, echoed in /me) is the
// durable copy; localStorage is a per-uid cache so every read stays synchronous.
// AuthContext calls adoptLearnProfile() on login (hydrate cache from the server,
// or push a not-yet-synced local/legacy profile up) and releaseLearnProfile() on
// logout — so a shared device never leaks one account's trajectory to another,
// and a reinstall/new device gets the profile back from the server.

import { api } from "../api";
import type { Strategy } from "./strategy";
import { DEFAULT_STRATEGY, leagueAdjust } from "./strategy";
import type { LeagueResult } from "./league";

export type UserProfile = {
  scenarios?: string[]; // SCENARIOS keys, 1-2 chosen (legacy seed for strategy)
  strategy?: Strategy; // the adaptive focus route (source of truth once tuned)
  onboardedAt?: string; // ISO; presence = goals step passed (picked OR "later")
  // C1: who assembles the plan. "auto" = the strategy weaves all batches;
  // "manual" = the learner's own hand-picked set (manualIds, in pick order).
  // Switching modes ARCHIVES, never erases: both the strategy and the manual
  // set stay in the profile, and batch progress lives per-batch on the server,
  // so it is absolute across any number of switches.
  planMode?: PlanMode;
  manualIds?: number[];
  // League placement — lives IN the profile so it is account-scoped and synced
  // (it sets the default pace via getStrategy; lib/league.ts wraps these).
  league?: LeagueResult;
  leaguePrev?: LeagueResult;   // the result before the latest — for the "grew?" delta
  leagueSkipped?: boolean;
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

const LEGACY_KEY = "ee-profile";          // pre-account global key (single-user era)
const LEGACY_LEAGUE = "ee-league";
const LEGACY_LEAGUE_SKIP = "ee-league-skip";
const LEGACY_STREAK = "ee-streak";        // dead local streak (server streak replaced it)

let uid: number | null = null;
const keyFor = () => (uid != null ? `ee-profile:${uid}` : LEGACY_KEY);

// Debounced push of the whole blob — setProfile fires in bursts (drags, toggles).
let pushTimer: number | undefined;
function schedulePush(): void {
  if (uid == null) return;               // logged out → nothing to sync to
  window.clearTimeout(pushTimer);
  pushTimer = window.setTimeout(() => {
    void api.setLearnProfile(getProfile() as Record<string, unknown>);
  }, 800);
}

function read(key: string): UserProfile | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as UserProfile) : null;
  } catch {
    return null;
  }
}

/** Bind the profile to an account and reconcile server ↔ local ↔ legacy.
 *  Server non-empty → server wins (it's the durable cross-device copy).
 *  Server empty → adopt the local per-uid cache, else the pre-account legacy
 *  keys (first login on the old single-user device), and push that up. Legacy
 *  keys are consumed exactly once and removed so the NEXT account on this
 *  device starts clean instead of inheriting someone else's trajectory. */
export function adoptLearnProfile(userId: number, server: UserProfile | null | undefined): void {
  uid = userId;
  const legacy = read(LEGACY_KEY) ?? {};
  const legacyLeague = read(LEGACY_LEAGUE) as LeagueResult | null;
  if (legacyLeague) legacy.league = legacy.league ?? legacyLeague;
  try { if (localStorage.getItem(LEGACY_LEAGUE_SKIP) === "1") legacy.leagueSkipped = true; } catch { /* private */ }

  const serverHas = server && Object.keys(server).length > 0;
  if (serverHas) {
    try { localStorage.setItem(keyFor(), JSON.stringify(server)); } catch { /* private */ }
  } else {
    const local = read(keyFor()) ?? (Object.keys(legacy).length ? legacy : null);
    if (local) {
      try { localStorage.setItem(keyFor(), JSON.stringify(local)); } catch { /* private */ }
      void api.setLearnProfile(local as Record<string, unknown>);
    }
  }
  for (const k of [LEGACY_KEY, LEGACY_LEAGUE, LEGACY_LEAGUE_SKIP, LEGACY_STREAK]) {
    try { localStorage.removeItem(k); } catch { /* private */ }
  }
}

/** Unbind on logout: reads return {} until the next account adopts. The per-uid
 *  cache stays (same account re-login on this device is instant + offline-safe). */
export function releaseLearnProfile(): void {
  window.clearTimeout(pushTimer);
  uid = null;
}

export function getProfile(): UserProfile {
  return read(keyFor()) ?? {};
}

export function setProfile(patch: Partial<UserProfile>): UserProfile {
  const next = { ...getProfile(), ...patch };
  try {
    localStorage.setItem(keyFor(), JSON.stringify(next));
  } catch {
    /* storage disabled — profile is non-critical */
  }
  schedulePush();
  return next;
}

export function isOnboarded(): boolean {
  return !!getProfile().onboardedAt;
}

// The active strategy: an explicitly tuned one wins; otherwise derive it from the
// onboarding picks (SCENARIOS keys are focus keys); otherwise the default. Until
// the learner tunes the path themselves, the league placement (if taken) sets the
// starting intensity + sprint size — the test result shapes the programme (B2).
export function getStrategy(): Strategy {
  const p = getProfile();
  if (p.strategy?.main) return { ...DEFAULT_STRATEGY, ...p.strategy };
  const pace = p.league ? leagueAdjust(p.league.tier) : {};
  const picks = (p.scenarios ?? []).filter(Boolean);
  if (picks.length)
    return { ...DEFAULT_STRATEGY, ...pace, main: picks[0], secondary: picks.slice(1, 4) };
  return { ...DEFAULT_STRATEGY, ...pace };
}

// True while the sprint pace comes from the league result (nothing hand-tuned yet)
// — lets Tune-your-path label WHY the defaults look the way they do.
export function paceFromLeague(): boolean {
  const p = getProfile();
  return !p.strategy?.main && !!p.league;
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
