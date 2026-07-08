import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api";
import Coachmarks from "./Coachmarks";
import { markTourSeen, tourForPath, tourSeen, type ScreenTour } from "./tours";

type Media = Record<string, { video: string; poster?: string }>;

/** Mounted once in the shell. Fires a screen's coach-mark tour the first time the
 *  user lands there (after a short beat so the screen has animated in), one at a
 *  time. The per-step video slots are filled from the server manifest if present. */
export default function RouteTour({ uid }: { uid: string | number }) {
  const { pathname } = useLocation();
  const [active, setActive] = useState<ScreenTour | null>(null);
  const [media, setMedia] = useState<Media>({});
  const fetched = useRef(false);

  useEffect(() => {
    if (fetched.current) return;
    fetched.current = true;
    api.tutorialManifest().then(setMedia).catch(() => {});
  }, []);

  useEffect(() => {
    if (active) return;
    const tour = tourForPath(pathname);
    if (!tour || tourSeen(uid, tour.id)) return;
    const id = window.setTimeout(() => setActive(tour), 650);
    return () => window.clearTimeout(id);
  }, [pathname, uid, active]);

  // Leaving the screen mid-tour cancels it (NOT marked seen — it refires on the
  // next visit). Otherwise the dimmed coach-mark follows the user onto a route
  // where its target elements don't exist and just sits there as a stuck modal.
  useEffect(() => {
    if (active && !active.match(pathname)) setActive(null);
  }, [pathname, active]);

  if (!active) return null;
  return (
    <Coachmarks
      steps={active.steps}
      media={media}
      onDone={() => { markTourSeen(uid, active.id); setActive(null); }}
    />
  );
}
