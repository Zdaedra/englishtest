// "Check your English league" — the pre-paywall placement test. Not a CEFR
// grammar quiz: every option below is CORRECT English. The test measures the
// gap the product sells — between correct-but-textbook phrasing and what a
// native executive would actually say. Content is deliberately English-only
// (it's a test OF English for B1+ users); chrome strings live in i18n.
import { getProfile, setProfile } from "./profile";

export type LeagueOption = { text: string; native?: boolean };
export type LeagueQ = { id: string; situation: string; options: LeagueOption[] };

export const LEAGUE_QS: LeagueQ[] = [
  {
    id: "pushback",
    situation: "A colleague presents a plan you find risky. You want to push back without killing the discussion.",
    options: [
      { text: "I think this plan is too risky." },
      { text: "Let me play devil's advocate here for a second.", native: true },
      { text: "I'm not sure this is a good idea." },
      { text: "I disagree with some parts of the plan." },
    ],
  },
  {
    id: "deadline",
    situation: "Your CEO asks if the project will be done by Friday. It won't be.",
    options: [
      { text: "No, it's impossible, we need more time." },
      { text: "I am sorry, but the deadline is very difficult." },
      { text: "We're not going to make Friday — here's where we actually are.", native: true },
      { text: "Maybe. We will try our best." },
    ],
  },
  {
    id: "circles",
    situation: "The meeting has been circling the same argument for twenty minutes.",
    options: [
      { text: "Let's move on to the next topic, please." },
      { text: "We are wasting time, let's decide something." },
      { text: "Can we finish this discussion?" },
      { text: "I think we're going in circles — let me try to land this.", native: true },
    ],
  },
  {
    id: "intro",
    situation: "You're introduced to a senior investor at a dinner.",
    options: [
      { text: "I've been looking forward to putting a face to the name.", native: true },
      { text: "Nice to meet you, I have heard many good things about you." },
      { text: "Hello, it is a pleasure to meet such an important person." },
      { text: "Hi, how are you doing tonight?" },
    ],
  },
  {
    id: "discount",
    situation: "A client keeps pushing for a discount you can't give.",
    options: [
      { text: "Unfortunately, a discount is not possible for us." },
      { text: "I can't give you a discount, sorry." },
      { text: "I will ask my manager about the discount." },
      { text: "The price is the price — but here's what I can do instead.", native: true },
    ],
  },
  {
    id: "backup",
    situation: "Your teammate's idea just got shot down harshly. You want to back them up.",
    options: [
      { text: "I think his idea was actually good." },
      { text: "Hang on — I don't think we gave that idea a fair shake.", native: true },
      { text: "Don't be so hard on him, please." },
      { text: "Let's respect each other's opinions." },
    ],
  },
  {
    id: "wrapup",
    situation: "You need to end a call that's running over.",
    options: [
      { text: "Sorry, I have to go now, I have another meeting." },
      { text: "I'm afraid we have to stop here." },
      { text: "Time is up, let's finish." },
      { text: "I want to be respectful of everyone's time — let's pick this up on Thursday.", native: true },
    ],
  },
];

// Four leagues over 0..7 native picks. Keys feed i18n: league.name.<key> etc.
export type LeagueTier = "functional" | "confident" | "sharp" | "native";
export function leagueOf(nativePicks: number): LeagueTier {
  if (nativePicks <= 1) return "functional";
  if (nativePicks <= 3) return "confident";
  if (nativePicks <= 5) return "sharp";
  return "native";
}

export type LeagueResult = {
  tier: LeagueTier;
  score: number;          // native picks, 0..LEAGUE_QS.length
  missed: string[];       // the native phrases the learner didn't choose
  at: string;             // ISO
};

// Tier ladder, low → high. Lets the result screen tell the learner whether they
// GREW since last time (the whole point of retaking a placement).
export const TIER_RANK: Record<LeagueTier, number> = {
  functional: 0, confident: 1, sharp: 2, native: 3,
};

// Retest cadence: a placement is only meaningful to repeat once enough learning
// has happened. 5 weeks — long enough to move a tier, short enough to stay a habit.
export const RETEST_DAYS = 35;

// Storage lives INSIDE the learning profile (lib/profile.ts) — account-scoped
// and server-synced, so the tier follows the user across devices and can never
// leak to another account on a shared browser. These wrappers keep the old API.
export function getLeagueResult(): LeagueResult | null {
  return getProfile().league ?? null;
}

// The result immediately BEFORE the latest — the comparison point for the
// "you grew" delta on the result screen. Null on the first-ever test.
export function getLeaguePrev(): LeagueResult | null {
  return getProfile().leaguePrev ?? null;
}

// Save a fresh result, shifting the current one into `leaguePrev` so a retake can
// show the before→after delta. Same test each time (a STABLE placement set is
// what makes the tiers comparable across attempts).
export function saveLeagueResult(r: LeagueResult): void {
  const prev = getProfile().league;
  setProfile({ league: r, leaguePrev: prev ?? undefined });
}

// Days since the last placement, or null if never taken.
export function daysSinceLeague(): number | null {
  const at = getProfile().league?.at;
  if (!at) return null;
  const ms = Date.now() - new Date(at).getTime();
  return ms >= 0 ? Math.floor(ms / 86_400_000) : 0;
}

// The home "retest your league" nudge fires once a result exists AND it has gone
// stale (≥ RETEST_DAYS). Distinct from the first-run entry card (which shows only
// when NO result exists), so the two are never on screen together.
export function leagueRetestDue(): boolean {
  const d = daysSinceLeague();
  return d != null && d >= RETEST_DAYS;
}

// The home entry card retires when the test is DONE or explicitly skipped —
// it must never be a permanent fixture on the home screen. (Retake stays
// available from the Profile screen's league row.)
export function dismissLeagueCard(): void {
  setProfile({ leagueSkipped: true });
}

export function leagueCardHidden(): boolean {
  const p = getProfile();
  return !!p.league || !!p.leagueSkipped;
}
