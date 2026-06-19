import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { api, BatchListItem, BatchMastery } from "../api";
import { orderedSections, SECTION_BY_SLUG, sectionName } from "../lib/sections";
import { getProgress } from "../lib/progress";
import { getProfile, getStrategy, isOnboarded, prioritySectionSlugs } from "../lib/profile";
import { buildSprint, weightMix } from "../lib/strategy";
import { BatchCover } from "../ui/Art";
import { IconArrowUp, IconCheck, IconPlay, IconRefresh, IconWave } from "../ui/icons";
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
      const rootRect = root.getBoundingClientRect();
      const pts = Array.from(
        root.querySelectorAll<HTMLElement>(".mnode")
      ).map((el) => {
        const r = el.getBoundingClientRect();
        return {
          x: r.left - rootRect.left + r.width / 2,
          top: r.top - rootRect.top,
          bottom: r.bottom - rootRect.top,
        };
      });
      setBox((prev) => {
        const next = { w: rootRect.width, h: root.scrollHeight };
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

    measure();
    const ro = new ResizeObserver(schedule);
    ro.observe(root);
    const imgs = Array.from(root.querySelectorAll("img"));
    imgs.forEach((img) => {
      if (!(img as HTMLImageElement).complete)
        img.addEventListener("load", schedule);
    });
    const fonts = (document as Document & { fonts?: { ready?: Promise<unknown> } })
      .fonts;
    let alive = true;
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
  const activeRef = useRef<HTMLDivElement | null>(null);

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

  // The spine: sections ordered by the learner's chosen scenarios first, then the
  // natural order; batches within a section oldest-first. Empty sections drop out.
  const chapters = useMemo(() => {
    const bySection = new Map<string, BatchListItem[]>();
    for (const b of batches) {
      if (!b.section) continue;
      const arr = bySection.get(b.section) ?? [];
      arr.push(b);
      bySection.set(b.section, arr);
    }
    const natural = orderedSections().map((s) => s.slug);
    const order = prioritySectionSlugs(getProfile(), natural);
    return order
      .map((slug) => SECTION_BY_SLUG[slug])
      .filter((s): s is NonNullable<typeof s> => !!s)
      .map((s) => ({
        section: s,
        items: (bySection.get(s.slug) ?? []).sort((a, b) =>
          a.created_at.localeCompare(b.created_at)
        ),
      }))
      .filter((c) => c.items.length > 0);
  }, [batches]);

  const flat = useMemo(() => chapters.flatMap((c) => c.items), [chapters]);
  const closed = (id: number) => !!getProgress(id).l3_passed;

  // Exactly one active node: the first not-yet-closed batch on the spine.
  const activeId = useMemo(() => {
    for (const b of flat) if (!closed(b.id)) return b.id;
    return null; // everything closed
  }, [flat]);

  const stateOf = (id: number): NodeState =>
    closed(id) ? "completed" : id === activeId ? "active" : "locked";

  const total = flat.length;
  const doneCount = flat.filter((b) => closed(b.id)).length;

  // The adaptive focus route: a small weighted sprint instead of all 89 at once.
  // Rebuilds live whenever the learner re-tunes (getStrategy reads the profile).
  const strategy = useMemo(() => getStrategy(), [batches]);
  const mix = useMemo(() => weightMix(strategy), [strategy, lang]);
  const sprint = useMemo(
    () => buildSprint(strategy, batches, (id) => !!getProgress(id).l3_passed),
    [strategy, batches]
  );
  const sprintActiveId = sprint[0]?.id ?? null;

  // Adaptive review. A node is "due" only if it's closed AND its recall has a real
  // signal that has drifted: low rolling average, or gone stale. Never re-locks.
  const masteryById = useMemo(
    () => new Map(mastery.map((m) => [m.batch_id, m] as const)),
    [mastery]
  );

  // Per-domain "presence" competence: share of a domain's phrases recalled at
  // familiar/automatic (CEFR can-do feel, sober — not a game HUD). Only domains
  // the learner has actually touched appear, so it never reads all-zero.
  const domains = useMemo(() => {
    return chapters
      .map((c) => {
        let total = 0, mastered = 0, shaky = 0;
        for (const b of c.items) {
          total += b.phrase_count || 0;
          const srs = masteryById.get(b.id)?.srs || {};
          mastered += (srs.familiar || 0) + (srs.automatic || 0);
          shaky += srs.shaky || 0;
        }
        return { slug: c.section.slug, name: sectionName(c.section.slug),
                 total, mastered, shaky, pct: total ? mastered / total : 0 };
      })
      .filter((d) => d.mastered + d.shaky > 0)
      .sort((a, b) => b.pct - a.pct)
      .slice(0, 6);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapters, masteryById, lang]);

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

  // The review rail: most-urgent first (weakest recall, then stalest), capped so it
  // stays a glanceable nudge rather than a second backlog.
  const dueList = useMemo(() => {
    return flat
      .map((b) => ({ b, reason: dueReason(b.id), m: masteryById.get(b.id) }))
      .filter((x): x is { b: BatchListItem; reason: "weak" | "stale"; m: BatchMastery } =>
        x.reason !== null)
      .sort((a, b) => {
        const av = a.m.avg_score ?? 99;
        const bv = b.m.avg_score ?? 99;
        if (av !== bv) return av - bv; // weakest recall first
        return daysSince(a.m.last_seen_at) > daysSince(b.m.last_seen_at) ? -1 : 1; // then stalest
      })
      .slice(0, 6);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flat, masteryById]);

  // Centre the current node so "where am I" is answered on open.
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "center" });
  }, [activeId, total]);

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
      <div className="screen-head">
        <h1 className="app-title">{t("nav.learn")}</h1>
        <p className="app-sub">{t("learn.sub")}</p>
        {total > 0 && (
          <p className="path-meta">{t("learn.progress", { done: doneCount, total })}</p>
        )}
        <p className="learn-note">{t("learn.note")}</p>
      </div>

      {/* Training Focus — the live, re-tunable strategy control (consilium design). */}
      <button className="focus-card" onClick={() => nav("/tune")}>
        <div className="focus-head">
          <span className="focus-kicker">{t("learn.focusKicker")}</span>
          <span className="focus-adjust">{t("learn.adjust")}</span>
        </div>
        <div className="focus-mix">
          {mix.map((m, i) => (
            <span key={i} className="focus-chip">{m.label} · {m.pct}%</span>
          ))}
        </div>
      </button>

      {/* Per-domain "presence" competence rings — a sober skills profile, not a HUD. */}
      {domains.length > 0 && (
        <div className="presence">
          <p className="section-label">{t("learn.presence")}</p>
          <div className="presence-row">
            {domains.map((d) => {
              const C = 2 * Math.PI * 22;
              const dash = Math.max(0, Math.min(1, d.pct)) * C;
              return (
                <button key={d.slug} className="presence-ring" onClick={() => nav(`/section/${d.slug}`)}>
                  <span className="presence-disc">
                    <svg viewBox="0 0 52 52" width="52" height="52" aria-hidden="true">
                      <circle cx="26" cy="26" r="22" fill="none" stroke="var(--hairline)" strokeWidth="4" />
                      <circle cx="26" cy="26" r="22" fill="none" stroke="var(--mark)" strokeWidth="4"
                        strokeLinecap="round" strokeDasharray={`${dash} ${C}`} transform="rotate(-90 26 26)" />
                      <text x="26" y="26" textAnchor="middle" dominantBaseline="central" className="presence-pct">
                        {Math.round(d.pct * 100)}
                      </text>
                    </svg>
                    {d.shaky > 0 && <span className="presence-shaky">{d.shaky}</span>}
                  </span>
                  <span className="presence-name">{d.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Confidence check — phrases you swiped "known" but never said aloud.
          Surfacing the self-vs-objective gap is the top self-study insight. */}
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

      {/* Current sprint — the small active set under the chosen focus, not all 89. */}
      {sprint.length > 0 && (
        <div className="sprint-block">
          <div className="review-head">
            <div className="review-head-main">
              <span className="review-title">{t("learn.sprintTitle")}</span>
              <span className="review-sub">{t("learn.sprintSub", { n: sprint.length })}</span>
            </div>
          </div>
          <div className="review-rail">
            {sprint.map((b) => (
              <button className="review-card" key={b.id} onClick={() => nav(`/batch/${b.id}`)}>
                <span className="review-thumb">
                  <BatchCover seed={b.slug} coverUrl={b.cover_url} locked={b.locked} />
                  {b.id === sprintActiveId && (
                    <span className="review-badge play"><IconPlay size={14} /></span>
                  )}
                </span>
                <span className="review-card-title">{b.title}</span>
                <span className="review-card-hint">
                  {b.id === sprintActiveId ? t("learn.continue") : t("learn.queued")}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {dueList.length > 0 && (
        <div className="review-block">
          <div className="review-head">
            <div className="review-head-main">
              <span className="review-title">{t("learn.reviewTitle")}</span>
              <span className="review-sub">{t("learn.reviewSub")}</span>
            </div>
            <span className="review-count">{dueList.length}</span>
          </div>
          <div className="review-rail">
            {dueList.map(({ b, reason }) => (
              <button
                className="review-card"
                key={b.id}
                onClick={() => nav(`/batch/${b.id}`)}
              >
                <span className="review-thumb">
                  <BatchCover seed={b.slug} coverUrl={b.cover_url} locked={b.locked} />
                  <span className="review-badge"><IconRefresh size={15} /></span>
                </span>
                <span className="review-card-title">{b.title}</span>
                <span className="review-card-hint">
                  {reason === "weak" ? t("learn.recallWeak") : t("learn.longAgo")}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {chapters.length > 0 && (
        <p className="section-label atlas-label">{t("learn.atlas")}</p>
      )}

      <div className="map">
        {chapters.map((c) => {
          const cDone = c.items.filter((b) => closed(b.id)).length;
          // How far the road is travelled in this section: up to the last node
          // that's been reached (completed or active). `reached` is that node's
          // index, which also equals the count of connector segments leading into
          // it — so the green fills exactly that many whole segments and lands on
          // the active node.
          let reached = -1;
          c.items.forEach((b, i) => {
            if (stateOf(b.id) !== "locked") reached = i;
          });
          return (
            <div className="map-chapter" key={c.section.slug}>
              <div className="topic-header">
                <div className="topic-head-main">
                  <span className="topic-kicker">{t("learn.chapterKicker")}</span>
                  <span className="topic-name">{sectionName(c.section.slug)}</span>
                </div>
                <span className="topic-count">{cDone}/{c.items.length}</span>
              </div>

              <div className="map-nodes">
                <MapTrack
                  done={reached}
                  sig={`${c.items.length}|${reached}|${activeId ?? -1}`}
                />
                {c.items.map((b) => {
                  gi += 1;
                  const st = stateOf(b.id);
                  const due = st === "completed" && isDue(b.id);
                  const side = gi % 2 === 0 ? "left" : "right";
                  return (
                    <div
                      className={`map-row ${side}`}
                      key={b.id}
                      ref={st === "active" ? activeRef : undefined}
                    >
                      <div className="map-node-wrap">
                        {st === "active" && <span className="map-bubble">{t("learn.continue")}</span>}
                        <button
                          className={`mnode ${st}${due ? " due" : ""}`}
                          onClick={() => nav(`/batch/${b.id}`)}
                        >
                          <span className="mnode-art">
                            <BatchCover seed={b.slug} coverUrl={b.cover_url} locked={b.locked} />
                          </span>
                          <span className="mnode-badge"><IconWave size={18} /></span>
                          {st === "completed" && (
                            <span className={`mnode-check${due ? " due-seal" : ""}`}>
                              {due ? <IconRefresh size={15} /> : <IconCheck size={15} />}
                            </span>
                          )}
                        </button>
                        <span className="mnode-label">{b.title}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}

        {chapters.length > 0 && (
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
