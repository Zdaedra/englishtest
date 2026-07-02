// Coach-mark tutorial: contextual steps that fire the first time a user lands on a
// screen (Duolingo model — NOT one big upfront tour). Each step points an arrow +
// short caption at a real element tagged with `data-tour="<target>"`. The same
// <target> key is the video filename on the server, so a clip dropped at
// /tutorial/<target>.mp4 auto-fills that step's slot (see routers/tutorial.py).

export type TourStep = {
  target: string;     // data-tour key (also the server video key)
  titleKey: string;   // i18n
  bodyKey: string;    // i18n
};

export type ScreenTour = {
  id: string;                         // persistence key
  match: (path: string) => boolean;   // which route this tour belongs to
  steps: TourStep[];
};

export const TOURS: ScreenTour[] = [
  {
    id: "library",
    match: (p) => p === "/",
    steps: [
      { target: "hero", titleKey: "tour.hero.t", bodyKey: "tour.hero.b" },
      { target: "nav", titleKey: "tour.nav.t", bodyKey: "tour.nav.b" },
    ],
  },
  {
    id: "practice",
    match: (p) => p.startsWith("/practice"),
    steps: [
      { target: "card", titleKey: "tour.card.t", bodyKey: "tour.card.b" },
      { target: "mic", titleKey: "tour.mic.t", bodyKey: "tour.mic.b" },
      { target: "handsfree", titleKey: "tour.hf.t", bodyKey: "tour.hf.b" },
    ],
  },
];

const key = (uid: string | number, id: string) => `ee-tour-${id}-${uid}`;

export function tourSeen(uid: string | number, id: string): boolean {
  try { return localStorage.getItem(key(uid, id)) === "1"; } catch { return false; }
}
export function markTourSeen(uid: string | number, id: string): void {
  try { localStorage.setItem(key(uid, id), "1"); } catch { /* noop */ }
}
/** "Replay tutorial" — clear every screen's seen-flag so the tours fire again. */
export function resetTours(uid: string | number): void {
  try { TOURS.forEach((t) => localStorage.removeItem(key(uid, t.id))); } catch { /* noop */ }
}
export function tourForPath(path: string): ScreenTour | undefined {
  return TOURS.find((t) => t.match(path));
}
