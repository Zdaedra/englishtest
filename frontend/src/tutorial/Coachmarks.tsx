import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useI18n } from "../i18n";
import { mediaUrl } from "../api";
import type { TourStep } from "./tours";

type Media = { video: string; poster?: string };
type Box = { x: number; y: number; w: number; h: number };
type Props = { steps: TourStep[]; media: Record<string, Media>; onDone: () => void };

const PAD = 8;       // spotlight padding around the element
const GAP = 22;      // distance between caption and the spotlight (the arrow lives here)

/** First-launch coach marks: dims the screen, cuts a spotlight over one real element
 *  (tagged data-tour), and points an arrow + short caption at it. Tap or swipe to
 *  advance; skip ends the tour. A per-step video slot fills if the server has a clip. */
export default function Coachmarks({ steps, media, onDone }: Props) {
  const { t } = useI18n();
  const [i, setI] = useState(0);
  const [box, setBox] = useState<Box | null>(null);
  const [, force] = useState(0);
  const startX = useRef(0);
  const step = steps[i];

  const advance = useCallback(() => {
    setI((n) => { if (n >= steps.length - 1) { onDone(); return n; } return n + 1; });
  }, [steps.length, onDone]);

  const measure = useCallback(() => {
    const el = step && document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
    if (!el) { setBox(null); return; }
    const r = el.getBoundingClientRect();
    setBox({ x: r.left, y: r.top, w: r.width, h: r.height });
  }, [step]);

  // Resolve the target (it may still be mounting); scroll it into view, then measure.
  // If it never appears (e.g. the mic is hidden for non-AI users) skip the step.
  useLayoutEffect(() => {
    let raf = 0, tries = 0;
    const find = () => {
      const el = document.querySelector<HTMLElement>(`[data-tour="${step?.target}"]`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
        raf = requestAnimationFrame(() => { raf = requestAnimationFrame(measure); });
      } else if (tries++ < 10) {
        raf = requestAnimationFrame(find);
      } else {
        advance();
      }
    };
    find();
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i]);

  useEffect(() => {
    const onMove = () => { measure(); force((x) => x + 1); };
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, true);
    return () => { window.removeEventListener("resize", onMove); window.removeEventListener("scroll", onMove, true); };
  }, [measure]);

  if (!step) return null;

  const vw = window.innerWidth, vh = window.innerHeight;
  const m = media[step.target];
  const below = box ? (box.y + box.h / 2) < vh * 0.5 : true;          // caption side
  const capW = Math.min(300, vw - 32);
  const cx = box
    ? Math.min(Math.max(box.x + box.w / 2, capW / 2 + 16), vw - capW / 2 - 16)
    : vw / 2;
  const capLeft = cx - capW / 2;
  const capTop = box ? (below ? box.y + box.h + PAD + GAP : undefined) : vh * 0.42;
  const capBottom = box && !below ? (vh - (box.y - PAD) + GAP) : undefined;

  // The single short arrow, living in the GAP between caption and element.
  const edgeY = box ? (below ? box.y + box.h + PAD : box.y - PAD) : 0;
  const aStart = box ? { x: cx, y: below ? (capTop as number) - 6 : (vh - (capBottom as number)) + 6 } : { x: 0, y: 0 };
  const aEnd = box ? { x: box.x + box.w / 2, y: below ? edgeY + 4 : edgeY - 4 } : { x: 0, y: 0 };

  const overlay = (
    <div className="cm-root" role="dialog" aria-modal="true"
         onPointerDown={(e) => { startX.current = e.clientX; }}
         onPointerUp={(e) => { if (Math.abs(e.clientX - startX.current) >= 0) advance(); }}>
      <svg className="cm-svg" width={vw} height={vh} viewBox={`0 0 ${vw} ${vh}`} aria-hidden="true">
        <defs>
          <mask id="cm-mask">
            <rect x="0" y="0" width={vw} height={vh} fill="white" />
            {box && <rect x={box.x - PAD} y={box.y - PAD} width={box.w + 2 * PAD} height={box.h + 2 * PAD} rx="14" fill="black" />}
          </mask>
          <marker id="cm-arrow" markerWidth="9" markerHeight="9" refX="5.5" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="rgba(255,255,255,0.95)" />
          </marker>
        </defs>
        <rect x="0" y="0" width={vw} height={vh} fill="rgba(20,16,10,0.66)" mask="url(#cm-mask)" />
        {box && (
          <rect x={box.x - PAD} y={box.y - PAD} width={box.w + 2 * PAD} height={box.h + 2 * PAD}
                rx="14" fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="2" />
        )}
        {box && (
          <line x1={aStart.x} y1={aStart.y} x2={aEnd.x} y2={aEnd.y}
                stroke="rgba(255,255,255,0.92)" strokeWidth="2.5" strokeLinecap="round" markerEnd="url(#cm-arrow)" />
        )}
      </svg>

      <div className="cm-cap" style={{ left: capLeft, width: capW, top: capTop, bottom: capBottom }}>
        {m && (
          <video className="cm-video" src={mediaUrl(m.video) || undefined}
                 poster={m.poster ? mediaUrl(m.poster) || undefined : undefined}
                 muted autoPlay loop playsInline />
        )}
        <div className="cm-title">{t(step.titleKey)}</div>
        <div className="cm-body">{t(step.bodyKey)}</div>
        <div className="cm-foot">
          <div className="cm-dots">{steps.map((_, k) => <span key={k} className={k === i ? "on" : ""} />)}</div>
          <button className="cm-skip" onPointerUp={(e) => { e.stopPropagation(); onDone(); }}
                  onClick={(e) => e.stopPropagation()}>{t("tour.skip")}</button>
        </div>
      </div>
    </div>
  );
  return createPortal(overlay, document.body);
}
