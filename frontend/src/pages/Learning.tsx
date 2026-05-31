import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { api, BatchListItem, BatchMastery } from "../api";
import { orderedSections, SECTION_BY_SLUG } from "../lib/sections";
import { getProgress } from "../lib/progress";
import { getProfile, isOnboarded, prioritySectionSlugs } from "../lib/profile";
import { BatchCover } from "../ui/Art";
import { IconArrowUp, IconCheck, IconRefresh, IconWave } from "../ui/icons";

type NodeState = "completed" | "active" | "locked";

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

  // Adaptive review. A node is "due" only if it's closed AND its recall has a real
  // signal that has drifted: low rolling average, or gone stale. Never re-locks.
  const masteryById = useMemo(
    () => new Map(mastery.map((m) => [m.batch_id, m] as const)),
    [mastery]
  );
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

  const jumpToActive = () =>
    activeRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });

  if (err) return <div className="screen"><p className="error">{err}</p></div>;

  let gi = -1; // running node index for the alternating serpentine

  return (
    <div className="screen map-screen">
      <div className="screen-head">
        <h1 className="app-title">Обучение</h1>
        <p className="app-sub">Твоя карта навыков — узел за узлом.</p>
      </div>

      {total > 0 && (
        <div className="path-progress">
          <div className="pp-bar">
            <span style={{ width: `${total ? (doneCount / total) * 100 : 0}%` }} />
          </div>
          <div className="pp-meta">Закрыто {doneCount} из {total}</div>
        </div>
      )}

      {dueList.length > 0 && (
        <div className="review-block">
          <div className="review-head">
            <div className="review-head-main">
              <span className="review-title">На повторение</span>
              <span className="review-sub">Подзабылось — освежи за пару минут.</span>
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
                  <BatchCover seed={b.slug} coverUrl={b.cover_url} />
                  <span className="review-badge"><IconRefresh size={15} /></span>
                </span>
                <span className="review-card-title">{b.title}</span>
                <span className="review-card-hint">
                  {reason === "weak" ? "Recall просел" : "Давно не трогал"}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="map">
        {chapters.map((c) => {
          const cDone = c.items.filter((b) => closed(b.id)).length;
          return (
            <div className="map-chapter" key={c.section.slug}>
              <div className="topic-header">
                <div className="topic-head-main">
                  <span className="topic-kicker">Раздел</span>
                  <span className="topic-name">{c.section.ru}</span>
                </div>
                <span className="topic-count">{cDone}/{c.items.length}</span>
              </div>

              <div className="map-nodes">
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
                        {st === "active" && <span className="map-bubble">Продолжить</span>}
                        <button
                          className={`mnode ${st}${due ? " due" : ""}`}
                          onClick={() => nav(`/batch/${b.id}`)}
                        >
                          <span className="mnode-art">
                            <BatchCover seed={b.slug} coverUrl={b.cover_url} />
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
          <div className="map-end">Дальше — новые разделы. Скоро.</div>
        )}
      </div>

      {total === 0 && !err && (
        <div className="empty"><p>Пока нечего проходить — батчи появятся здесь.</p></div>
      )}

      {/* Portaled to <body> so it's truly viewport-fixed: the routed screen keeps a
          residual transform from its entry animation, which would otherwise trap a
          position:fixed child inside the screen instead of the viewport. */}
      {activeId !== null &&
        createPortal(
          <button className="map-fab" onClick={jumpToActive} aria-label="К текущему узлу">
            <IconArrowUp size={26} />
          </button>,
          document.body
        )}
    </div>
  );
}
