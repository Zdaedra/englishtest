import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { api, BatchListItem, BatchMastery } from "../api";
import { orderedSections } from "../lib/sections";
import { getProgress } from "../lib/progress";
import { getProfile, getStrategy, isOnboarded, prioritySectionSlugs } from "../lib/profile";
import { buildTrajectory, focusBuckets } from "../lib/strategy";
import { BatchCover } from "../ui/Art";
import { BatchTapButton } from "../ui/BatchTapButton";
import { useProgressVersion } from "../ui/BatchMenu";
import { setQueueSiblings, clearQueueSiblings, runBatchAction } from "../lib/batchActions";
import { IconArrowUp, IconCheck, IconInfo, IconRefresh } from "../ui/icons";
import { useI18n } from "../i18n";

type NodeState = "completed" | "active" | "locked";

// The road. A measured SVG overlay that threads the section's nodes with rounded
// orthogonal connectors (metro-style elbows), reproducing the reference's
// serpentine where the line is a spine the nodes are strung onto — not a central
// rail they float beside. It is measure-based, not fixed-pitch, so it survives
// variable row heights (the active node carries a bubble; Russian labels wrap),
// and it re-measures on resize, web-font load and cover-image load so the road
// never drifts after async layout shifts. `frac` paints the travelled portion
// green; everything ahead stays a calm light gray.
//
// SIDE_SHIFT mirrors the `.map-row.left/.right .map-node-wrap` translateX in
// index.css. The road derives a node's column from this constant + its layout
// box, never from a transformed rect — keep the two in sync if the CSS changes.
const SIDE_SHIFT = 86;
function MapTrack({ done, sig }: { done: number; sig: string }) {
  const ref = useRef<SVGSVGElement | null>(null);
  const [paths, setPaths] = useState<{ full: string; done: string }>({
    full: "",
    done: "",
  });
  const [box, setBox] = useState({ w: 0, h: 0 });

  useLayoutEffect(() => {
    const svg = ref.current;
    const root = svg?.parentElement as HTMLElement | null | undefined;
    if (!root) return;

    let raf = 0;
    const measure = () => {
      // Anchors come from the LAYOUT box (offsetTop/offsetLeft), never
      // getBoundingClientRect. getBoundingClientRect bakes in CSS transforms —
      // and a reorder runs two of them at once (the side-flip's animated
      // translateX, plus the FLIP translate(dx,dy)). Measuring during those put
      // the moved node's connector in the wrong column, which is what broke the
      // road. offsetTop/offsetLeft are transform-immune, so each node reports its
      // RESTING slot regardless of any in-flight animation: the road is a fixed
      // track and tiles glide onto it. This is the hard-anchored connector model
      // (PowerPoint-style): every node exposes a fixed top-centre (entry) and
      // bottom-centre (exit), and segments are rebuilt from those anchors.
      const w = root.clientWidth;
      const pts = Array.from(
        root.querySelectorAll<HTMLElement>(".mnode")
      ).map((el) => {
        let x = 0, top = 0;
        let p: HTMLElement | null = el;
        while (p && p !== root) {
          top += p.offsetTop;
          x += p.offsetLeft;
          p = p.offsetParent as HTMLElement | null;
        }
        // offsetLeft ignores the wrap's resting translateX(±SIDE_SHIFT), so add
        // it back from the side the layout assigned — that is the real column.
        const wrap = el.closest<HTMLElement>(".map-node-wrap");
        const tx = wrap?.dataset.side === "left" ? -SIDE_SHIFT
          : wrap?.dataset.side === "right" ? SIDE_SHIFT : 0;
        return {
          x: x + el.offsetWidth / 2 + tx,
          top,
          bottom: top + el.offsetHeight,
        };
      });
      setBox((prev) => {
        const next = { w, h: root.scrollHeight };
        return prev.w === next.w && prev.h === next.h ? prev : next;
      });
      if (pts.length < 2) {
        setPaths((p) => (p.full === "" && p.done === "" ? p : { full: "", done: "" }));
        return;
      }
      // One rounded-orthogonal elbow per adjacent pair: exit the upper node's
      // bottom centre, corner to a short horizontal run that clears its label,
      // then a long drop into the lower node's top centre. Each segment is its own
      // subpath string so the "travelled" green can cover an EXACT whole number of
      // completed segments — it lands precisely on the active node rather than at a
      // uniform length-fraction that drifts when row heights differ (the active
      // node carries a taller bubble).
      const R = 16;
      const f = (v: number) => v.toFixed(1);
      const segs = pts.slice(0, -1).map((p, i) => {
        const n = pts[i + 1];
        const dir = n.x >= p.x ? 1 : -1;
        const y1 = p.bottom - 2;
        const runY = y1 + R;
        const y2 = n.top + 2;
        return (
          `M ${f(p.x)} ${f(y1)} ` +
          `Q ${f(p.x)} ${f(runY)} ${f(p.x + dir * R)} ${f(runY)} ` +
          `L ${f(n.x - dir * R)} ${f(runY)} ` +
          `Q ${f(n.x)} ${f(runY)} ${f(n.x)} ${f(runY + R)} ` +
          `L ${f(n.x)} ${f(y2)}`
        );
      });
      const full = segs.join(" ");
      const doneStr = segs.slice(0, Math.max(0, done)).join(" ");
      setPaths((prev) =>
        prev.full === full && prev.done === doneStr ? prev : { full, done: doneStr }
      );
    };
    const schedule = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(measure);
    };

    let alive = true;
    measure();
    // Re-measure only on genuine layout changes (label reflow, image load,
    // viewport). Reorders are caught by the effect's [sig] dependency, which
    // re-runs measure() against the freshly committed DOM. No transform-timing
    // band-aids are needed: offset-based anchors stay correct mid-animation.
    const ro = new ResizeObserver(() => schedule());
    ro.observe(root);
    const imgs = Array.from(root.querySelectorAll("img"));
    imgs.forEach((img) => {
      if (!(img as HTMLImageElement).complete)
        img.addEventListener("load", schedule);
    });
    const fonts = (document as Document & { fonts?: { ready?: Promise<unknown> } })
      .fonts;
    fonts?.ready?.then(() => alive && schedule());

    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      ro.disconnect();
      imgs.forEach((img) => img.removeEventListener("load", schedule));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  return (
    <svg
      ref={ref}
      className="map-track"
      width={box.w}
      height={box.h}
      viewBox={`0 0 ${box.w} ${box.h}`}
      aria-hidden="true"
    >
      {paths.full && <path className="map-track-bg" d={paths.full} />}
      {paths.done && (
        <path
          className="map-track-done"
          d={paths.done}
          pathLength={1}
        />
      )}
    </svg>
  );
}

// Adaptive review ("Закрепление"): a CLOSED batch resurfaces when recall drifts
// below the pass bar or the material goes cold. It never re-locks — the node stays
// completed, just flagged due — so "a miss re-queues but never re-locks" holds.
const REVIEW_AVG = 7; // below the L3 pass bar = recall has drifted
const STALE_DAYS = 14; // not drilled in two weeks = gone cold
const daysSince = (iso: string | null) =>
  iso ? (Date.now() - new Date(iso).getTime()) / 86_400_000 : Infinity;

// Focus-bucket visual identity. Color lives ONLY here (a small chip) — never on a
// wide bar — to keep the calm bronze/emerald palette (consilium decision). The main
// focus always reads bronze ("your focus"); business=slate, discovery=emerald.
type DomVariant = "main" | "secondary" | "business" | "discovery";
function domVariant(key: string): DomVariant {
  if (key === "business") return "business";
  if (key === "discovery") return "discovery";
  if (key === "secondary") return "secondary";
  return "main";
}
function ChipGlyph({ variant }: { variant: DomVariant }) {
  const p = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.9, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (variant === "business")
    return (<svg {...p}><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>);
  if (variant === "discovery")
    return (<svg {...p}><circle cx="12" cy="12" r="9" /><path d="M15.5 8.5l-2 5-5 2 2-5 5-2z" /></svg>);
  if (variant === "secondary")
    return (<svg {...p}><path d="M12 3l2.4 5.2 5.6.6-4.2 3.8 1.2 5.6L12 15.8 6.8 18l1.2-5.6L4 8.6l5.6-.6L12 3z" /></svg>);
  // main — a spark/charisma glyph
  return (<svg {...p}><path d="M12 3v5M12 16v5M3 12h5M16 12h5M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3" /></svg>);
}

// The Learning Map: the path itself is the product. Batches are nodes on a
// serpentine spine, grouped under dark "topic header" cards. Exactly one node is
// active (the resume point); everything before it is closed, everything after is
// locked. No level gates, no gamification — a calm map you read top to bottom.
export default function Learning() {
  const nav = useNavigate();
  const { t, lang } = useI18n();
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [mastery, setMastery] = useState<BatchMastery[]>([]);
  const [err, setErr] = useState("");
  const pv = useProgressVersion();   // re-render after a long-press menu action
  const activeRef = useRef<HTMLDivElement | null>(null);
  const [showInfo, setShowInfo] = useState(false);   // (i) → how learning works
  const [domOpen, setDomOpen] = useState(false);     // "Твои домены" expanded? (default collapsed)
  const [reordering, setReordering] = useState(false);   // global tap-reorder mode
  const flipPrev = useRef<Map<number, DOMRect>>(new Map());   // FLIP: node rects before a reorder
  const flipArmed = useRef(false);

  // No profile yet → send the learner through onboarding first.
  useEffect(() => {
    if (!isOnboarded()) {
      nav("/onboarding", { replace: true });
      return;
    }
    api.listBatches().then(setBatches).catch((e) => setErr(String(e)));
    // Mastery feeds the review rail; if it fails, the map still stands.
    api.getMastery().then(setMastery).catch(() => {});
  }, [nav]);

  // The plan: every batch woven into domain-apportioned SPRINTS (the configured
  // focus mix made visible), not grouped section-by-section. Strategy + focus
  // buckets drive the order; the whole field is laid out ahead.
  const strategy = useMemo(() => getStrategy(), [batches]);
  const buckets = useMemo(() => focusBuckets(strategy), [strategy, lang]);
  const sectionPriority = useMemo(
    () => prioritySectionSlugs(getProfile(), orderedSections().map((x) => x.slug)),
    [batches]
  );
  const traj = useMemo(
    () => buildTrajectory(strategy, batches, sectionPriority),
    [strategy, batches, sectionPriority]
  );
  // The computed order, with any manual drag (path_rank) layered on top as a
  // total override. Re-tuning domains clears path_rank, so the mix drives again.
  const flat = useMemo(() => {
    const baseIndex = new Map(traj.order.map((b, i) => [b.id, i] as const));
    return traj.order.slice().sort((a, b) => {
      const ra = getProgress(a.id).path_rank;
      const rb = getProgress(b.id).path_rank;
      const ka = ra == null ? baseIndex.get(a.id)! : ra;
      const kb = rb == null ? baseIndex.get(b.id)! : rb;
      if (ka !== kb) return ka - kb;
      return baseIndex.get(a.id)! - baseIndex.get(b.id)!;
    });
  }, [traj, pv]);
  const sprintSize = Math.max(1, strategy.sprintSize || 5);
  const sprints = useMemo(() => {
    const out: BatchListItem[][] = [];
    for (let i = 0; i < flat.length; i += sprintSize) out.push(flat.slice(i, i + sprintSize));
    return out;
  }, [flat, sprintSize]);

  // Register the WHOLE plan as one sibling list so the long-press menu's move
  // up/down/start/end act across sprint boundaries (cleared when we leave).
  useEffect(() => {
    const ids = flat.map((b) => b.id);
    const map: Record<number, number[]> = {};
    for (const id of ids) map[id] = ids;
    setQueueSiblings(map);
    return () => clearQueueSiblings();
  }, [flat]);

  // FLIP animation for reorder: capture node positions the instant a reorder fires
  // (DOM still in the old order — the event runs before React re-renders), then
  // animate each node from its old screen spot to its new one. Makes the queue move
  // glide (whether reordered by drag or the menu's up/down) instead of jumping.
  useEffect(() => {
    const capture = () => {
      const m = new Map<number, DOMRect>();
      document.querySelectorAll<HTMLElement>(".map-node-wrap[data-bid]")
        .forEach((el) => m.set(Number(el.dataset.bid), el.getBoundingClientRect()));
      flipPrev.current = m;
      flipArmed.current = true;
    };
    window.addEventListener("ee-progress-changed", capture);
    return () => window.removeEventListener("ee-progress-changed", capture);
  }, []);
  useLayoutEffect(() => {
    if (!flipArmed.current) return;
    flipArmed.current = false;
    const prev = flipPrev.current;
    document.querySelectorAll<HTMLElement>(".map-node-wrap[data-bid]").forEach((el) => {
      const old = prev.get(Number(el.dataset.bid));
      if (!old) return;
      const now = el.getBoundingClientRect();
      const dx = old.left - now.left, dy = old.top - now.top;
      if (!dx && !dy) return;
      // WAAPI, not CSS transition: the animation auto-reverts to the element's
      // resting CSS transform when it ends, so NOTHING is left inline. A stuck
      // inline transform was what knocked tiles off the road after a reorder.
      const sideX = el.dataset.side === "left" ? -86 : el.dataset.side === "right" ? 86 : 0;
      if (typeof el.animate === "function") {
        // Longer, app-standard --spring easing → a plush glide instead of a snap.
        // The travel distance scales the duration a touch so far moves don't feel
        // rushed and tiny nudges stay quick (clamped 360–620ms).
        const dist = Math.hypot(dx, dy);
        const dur = Math.max(360, Math.min(620, 360 + dist * 0.6));
        el.animate(
          [{ transform: `translateX(${sideX}px) translate(${dx}px, ${dy}px)` },
           { transform: `translateX(${sideX}px)` }],
          { duration: dur, easing: "cubic-bezier(.22, 1, .36, 1)" },
        );
      }
    });
  }, [pv]);

  const closed = (id: number) => !!getProgress(id).l3_passed;

  // Exactly one active node: the first not-yet-closed batch on the spine.
  const activeId = useMemo(() => {
    for (const b of flat) if (!closed(b.id)) return b.id;
    return null; // everything closed
  }, [flat]);

  const stateOf = (id: number): NodeState =>
    closed(id) ? "completed" : id === activeId ? "active" : "locked";

  const total = flat.length;

  // Per-sprint domain mix: how many batches of each focus bucket a sprint holds,
  // shown as small chips in the sprint header so the configured mix is visible.
  const bucketByKey = useMemo(() => new Map(buckets.map((b) => [b.key, b] as const)), [buckets]);
  const sprintMix = (items: BatchListItem[]) => {
    const counts = new Map<string, number>();
    for (const b of items) {
      const k = traj.domainOf.get(b.id) ?? "discovery";
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([key, n]) => ({ key, n, variant: domVariant(key), label: bucketByKey.get(key)?.label ?? "" }));
  };

  // Adaptive review. A node is "due" only if it's closed AND its recall has a real
  // signal that has drifted: low rolling average, or gone stale. Never re-locks.
  const masteryById = useMemo(
    () => new Map(mastery.map((m) => [m.batch_id, m] as const)),
    [mastery]
  );

  // Real competence per SECTION: (familiar+automatic)/total. Aggregated up to the
  // focus buckets below — the honest "where I actually am".
  const sectionComp = useMemo(() => {
    const m = new Map<string, { mastered: number; total: number }>();
    for (const b of batches) {
      if (!b.section) continue;
      const srs = masteryById.get(b.id)?.srs || {};
      const cur = m.get(b.section) ?? { mastered: 0, total: 0 };
      cur.total += b.phrase_count || 0;
      cur.mastered += (srs.familiar || 0) + (srs.automatic || 0);
      m.set(b.section, cur);
    }
    return m;
  }, [batches, masteryById]);

  // The "Твои домены" rows: focus allocation (intent) joined with real competence
  // (fact). The track fill = comp; a thin marker = focus pct. One honest story.
  const domainRows = useMemo(
    () =>
      buckets.map((bk) => {
        let mastered = 0, total = 0;
        for (const slug of bk.sections) {
          const c = sectionComp.get(slug);
          if (c) { mastered += c.mastered; total += c.total; }
        }
        return { ...bk, variant: domVariant(bk.key), comp: total ? mastered / total : 0 };
      }),
    [buckets, sectionComp]
  );

  const dueTotal = useMemo(() => mastery.reduce((s, m) => s + (m.due || 0), 0), [mastery]);

  // Confidence-calibration gap: phrases swiped "known" but not produced aloud.
  const gapCount = useMemo(() => mastery.reduce((s, m) => s + (m.gap || 0), 0), [mastery]);
  const dueReason = (id: number): "weak" | "stale" | null => {
    if (!closed(id)) return null;
    const m = masteryById.get(id);
    if (!m || m.avg_score == null) return null;
    if (m.avg_score < REVIEW_AVG) return "weak";
    if (daysSince(m.last_seen_at) >= STALE_DAYS) return "stale";
    return null;
  };
  const isDue = (id: number) => dueReason(id) !== null;

  // Open at the TOP (focus card + stats first), not jumped to the active node.
  // The floating "jump to active" FAB still rides the learner down on demand.

  // The jump FAB is a utility, not décor — it only appears once the learner has
  // scrolled away from the top, then quietly offers a ride back to the active node.
  const [showFab, setShowFab] = useState(false);
  useEffect(() => {
    const onScroll = () => setShowFab(window.scrollY > 260);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const jumpToActive = () =>
    activeRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });

  if (err) return <div className="screen"><p className="error">{err}</p></div>;

  let gi = -1; // running node index for the alternating serpentine

  return (
    <div className="screen map-screen">
      <div className="screen-head lh-head">
        <div className="lh-head-text">
          <h1 className="app-title">{t("nav.learn")}</h1>
          <p className="app-sub">{t("learn.sub")}</p>
        </div>
        <button className="lh-info" onClick={() => setShowInfo((v) => !v)}
          aria-label={t("learn.infoAria")} aria-expanded={showInfo}>
          <IconInfo size={20} />
        </button>
      </div>
      {showInfo && <p className="lh-note">{t("learn.note")}</p>}

      {/* Adaptive action-strip — "what to do now", shown ONLY when there's a real
          task (due review / confidence check). Never a standing notifications panel. */}
      {(dueTotal > 0 || gapCount > 0) && (
        <div className="act-strip">
          {dueTotal > 0 && (
            <button className="review-due refresh-card" onClick={() => nav("/practice", { state: { review: true } })}>
              <span className="review-due-ico"><IconRefresh size={19} /></span>
              <span className="review-due-text">
                <span className="review-due-title">{t("learn.reviewTitle")}</span>
                <span className="review-due-sub">{t("learn.reviewSub")}</span>
              </span>
              <span className="act-count">{dueTotal}</span>
              <span className="review-due-go">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
              </span>
            </button>
          )}
          {gapCount > 0 && (
            <button className="review-due calib-card" onClick={() => nav("/practice", { state: { gap: true } })}>
              <span className="review-due-ico">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="0.6" fill="currentColor" />
                </svg>
              </span>
              <span className="review-due-text">
                <span className="review-due-title">{t("calib.title")}</span>
                <span className="review-due-sub">{t("calib.sub", { n: gapCount })}</span>
              </span>
              <span className="review-due-go">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
              </span>
            </button>
          )}
        </div>
      )}

      {/* Твои домены — collapsed by default to a card the size of "На повторение".
          Expanded, it shows each domain's competence (fill) vs focus share (marker)
          and the link to re-tune the mix. */}
      {domainRows.length > 0 && (
        domOpen ? (
          <div className="dom-card">
            <div className="dom-head">
              <button className="dom-toggle" onClick={() => setDomOpen(false)} aria-expanded={true}>
                <span className="dom-kicker">{t("learn.domains")}</span>
                <svg className="dom-chev open" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 15l6-6 6 6" /></svg>
              </button>
              <button className="dom-adjust" onClick={() => nav("/tune")}>{t("learn.adjust")}</button>
            </div>
            {domainRows.map((d, i) => {
              const comp = Math.round(d.comp * 100);
              return (
                <div className={`dom-row ${d.variant}`} key={i}>
                  <span className="dom-ico"><ChipGlyph variant={d.variant} /></span>
                  <span className="dom-name">{d.label}</span>
                  <span className="dom-vals">
                    <span className="dom-pct">{comp}%</span>
                    <span className="dom-focus">{t("learn.focusShare", { n: d.pct })}</span>
                  </span>
                  <span className="dom-track">
                    <span className="dom-fill" style={{ width: `${comp > 0 ? Math.max(comp, 3) : 0}%` }} />
                    <span className="dom-marker" style={{ left: `${d.pct}%` }} />
                  </span>
                </div>
              );
            })}
            <div className="dom-legend">
              <span className="dom-leg"><span className="dom-leg-fill" />{t("learn.legendComp")}</span>
              <span className="dom-leg"><span className="dom-leg-mark" />{t("learn.legendFocus")}</span>
            </div>
          </div>
        ) : (
          <button className="review-due dom-collapsed" onClick={() => setDomOpen(true)} aria-expanded={false}>
            <span className="review-due-ico">
              <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h7M15 18h5" /><circle cx="16" cy="6" r="2" /><circle cx="8" cy="12" r="2" /><circle cx="13" cy="18" r="2" /></svg>
            </span>
            <span className="review-due-text">
              <span className="review-due-title">{t("learn.domains")}</span>
              <span className="review-due-sub">{t("learn.domainsSub")}</span>
            </span>
            <span className="review-due-go">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
            </span>
          </button>
        )
      )}

      {/* The plan header + a single global reorder toggle (move up/down across the
          whole plan; move-to-start/end live in the long-press menu). */}
      {sprints.length > 0 && (
        <div className="map-head">
          <p className="section-label atlas-label">{t("learn.plan")}</p>
          {flat.length > 1 && (
            reordering ? (
              <button className="map-reorder done" onClick={() => setReordering(false)}>
                {t("learn.reorderDone")}
              </button>
            ) : (
              <button className="map-reorder" onClick={() => setReordering(true)} aria-label={t("learn.reorder")}>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M8 4v16M8 4L5 7M8 4l3 3M16 20V4M16 20l-3-3M16 20l3-3" /></svg>
                <span>{t("learn.reorder")}</span>
              </button>
            )
          )}
        </div>
      )}

      <div className="map">
        {sprints.map((items, si) => {
          const cDone = items.filter((b) => closed(b.id)).length;
          // Road travel: up to the last reached (completed/active) node in this
          // sprint — that index = the number of whole connector segments to paint.
          let reached = -1;
          items.forEach((b, i) => {
            if (stateOf(b.id) !== "locked") reached = i;
          });
          const mix = sprintMix(items);
          return (
            <div className="map-chapter" key={`sprint-${si}`}>
              <div className="topic-header">
                <div className="topic-head-main">
                  <span className="topic-kicker">{t("learn.sprintKicker")}</span>
                  <span className="topic-name">{t("learn.sprintLabel", { n: si + 1 })}</span>
                  <span className="sprint-mix">
                    {mix.map((m) => (
                      <span className={`sprint-chip ${m.variant}`} key={m.key} title={m.label}>
                        <ChipGlyph variant={m.variant} />
                        <span className="sprint-chip-n">{m.n}</span>
                      </span>
                    ))}
                  </span>
                </div>
                <div className="topic-right">
                  <span className={`topic-count${cDone === items.length && items.length > 0 ? " done" : ""}`}>{cDone}/{items.length}</span>
                </div>
              </div>

              <div className="map-nodes">
                <MapTrack
                  done={reached}
                  sig={`${items.map((x) => x.id).join(",")}|${reached}|${activeId ?? -1}`}
                />
                {items.map((b, idx) => {
                  gi += 1;
                  const gIdx = si * sprintSize + idx;   // index in the whole plan
                  const st = stateOf(b.id);
                  const due = st === "completed" && isDue(b.id);
                  const side = gi % 2 === 0 ? "left" : "right";
                  const srs = masteryById.get(b.id)?.srs || {};
                  const learned = (srs.familiar || 0) + (srs.automatic || 0);
                  const tot = b.phrase_count || 0;
                  const variant = domVariant(traj.domainOf.get(b.id) ?? "discovery");
                  const art = (
                    <>
                      <span className="mnode-art">
                        <BatchCover seed={b.slug} coverUrl={b.cover_url} locked={b.locked} />
                      </span>
                      <span className={`mnode-dom ${variant}`} aria-hidden="true"><ChipGlyph variant={variant} /></span>
                      {tot > 0 && <span className="mnode-count">{learned}/{tot}</span>}
                    </>
                  );
                  return (
                    <div
                      className={`map-row ${side}`}
                      key={b.id}
                      ref={st === "active" ? activeRef : undefined}
                    >
                      <div className="map-node-wrap" data-bid={b.id} data-side={side}>
                        {st === "active" && !reordering && <span className="map-bubble">{t("learn.continue")}</span>}
                        {reordering ? (
                          <div className={`mnode ${st}${due ? " due" : ""} reordering`}>
                            {art}
                            <span className="mnode-reorder">
                              <button className="mnode-arrow" disabled={gIdx === 0}
                                aria-label={t("batch.menu.moveUp")}
                                onClick={() => runBatchAction(b.id, "moveUp")}>
                                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M6 11l6-6 6 6" /></svg>
                              </button>
                              <button className="mnode-arrow" disabled={gIdx === flat.length - 1}
                                aria-label={t("batch.menu.moveDown")}
                                onClick={() => runBatchAction(b.id, "moveDown")}>
                                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M6 13l6 6 6-6" /></svg>
                              </button>
                            </span>
                          </div>
                        ) : (
                          <BatchTapButton
                            className={`mnode ${st}${due ? " due" : ""}`}
                            batchId={b.id} title={b.title}
                          >
                            {art}
                            {st === "completed" && (
                              <span className={`mnode-check${due ? " due-seal" : ""}`}>
                                {due ? <IconRefresh size={15} /> : <IconCheck size={15} />}
                              </span>
                            )}
                          </BatchTapButton>
                        )}
                        <span className="mnode-label">{b.title}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}

        {sprints.length > 0 && (
          <div className="map-end">{t("learn.mapEnd")}</div>
        )}
      </div>

      {total === 0 && !err && (
        <div className="empty"><p>{t("learn.empty")}</p></div>
      )}

      {/* Portaled to <body> so it's truly viewport-fixed: the routed screen keeps a
          residual transform from its entry animation, which would otherwise trap a
          position:fixed child inside the screen instead of the viewport. */}
      {activeId !== null &&
        showFab &&
        createPortal(
          <button className="map-fab" onClick={jumpToActive} aria-label={t("learn.jumpAria")}>
            <IconArrowUp size={22} />
          </button>,
          document.body
        )}
    </div>
  );
}
