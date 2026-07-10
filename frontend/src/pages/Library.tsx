import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, BatchListItem, BatchMastery, PhraseSearchItem, WeeklySummary } from "../api";
import { usePlayer } from "../player/PlayerContext";
import { BatchCover } from "../ui/Art";
import { BatchTapButton } from "../ui/BatchTapButton";
import { useProgressVersion } from "../ui/BatchMenu";
import { IconSearch, IconPlay } from "../ui/icons";
import { orderedSections, sectionName } from "../lib/sections";
import { planFocus } from "../lib/plan";
import { getProgress, isActive } from "../lib/progress";
import { addManual, isInManual, removeManual } from "../lib/profile";
import { useTeach } from "../tutorial/teach";
import { getAvatar } from "../lib/avatar";
import { syncReviewReminder } from "../lib/reminders";
import { leagueCardHidden, dismissLeagueCard, leagueRetestDue, daysSinceLeague } from "../lib/league";
import { shouldNudgeWidget, markWidgetNudgeShown, dismissWidgetNudge } from "../lib/widgetNudge";
import WidgetHowto from "../ui/WidgetHowto";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";

const numOf = (slug: string) => {
  const m = slug.match(/(\d+)\s*$/);
  return m ? parseInt(m[1], 10) : 0;
};
const isClosed = (id: number) => !!getProgress(id).l3_passed;

export default function Library() {
  const nav = useNavigate();
  const loc = useLocation();
  const { t } = useI18n();
  const { user } = useAuth();
  const player = usePlayer();
  const pv = useProgressVersion();   // re-render after a long-press menu action
  const initials = ((user?.name?.trim() || user?.email || "")
    .split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map((s) => s[0]?.toUpperCase()).join("")) || "·";
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [err, setErr] = useState("");
  // Work streak: server truth only (days actually trained, with a freeze
  // bridge). Starts at 0 for a render tick — better than flashing the retired
  // local visit-counter's number, which measured opens, not work.
  const [streak, setStreak] = useState(0);
  // Spaced-repetition: how many practiced phrases are due to refresh right now.
  const [dueCount, setDueCount] = useState(0);
  // Moment of the day: how many phrases the user asked Live for recently.
  const [liveCount, setLiveCount] = useState(0);
  const [mastery, setMastery] = useState<BatchMastery[]>([]);
  // "Your week" rollup — shown once there's a meaningful amount of work in it.
  const [weekly, setWeekly] = useState<WeeklySummary | null>(null);
  // League placement test — the entry card retires after the first run or an
  // explicit skip; it must never squat on the home screen.
  const [leagueHidden, setLeagueHidden] = useState(() => leagueCardHidden());
  // League loop: once a result is ≥5 weeks old, nudge a retake to measure growth.
  const retestDue = leagueRetestDue();
  const retestDays = daysSinceLeague();
  // Widget nudge (native): suggest adding the lock-screen widget until it's
  // actually there — ≤5 times total, ≤1/day, dismissible (lib/widgetNudge).
  const [widgetNudge, setWidgetNudge] = useState(false);
  const [widgetHowto, setWidgetHowto] = useState(false);
  useEffect(() => {
    if (user?.id == null) return;
    let on = true;
    shouldNudgeWidget(user.id).then((ok) => {
      if (!on || !ok) return;
      markWidgetNudgeShown(user.id);
      setWidgetNudge(true);
    });
    return () => { on = false; };
  }, [user?.id]);
  const { tip } = useTeach();
  useEffect(() => { if (dueCount > 0) tip("refresh"); }, [dueCount, tip]);
  const [avatar, setAvatar] = useState<string | null>(null);

  // Search (opened from the floating nav's search button).
  const [searchOpen, setSearchOpen] = useState(false);
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const [phrases, setPhrases] = useState<PhraseSearchItem[] | null>(null);

  useEffect(() => {
    api.listBatches().then(setBatches).catch((e) => setErr(String(e)));
    api.getMastery()
      .then((ms) => {
        setMastery(ms);
        const due = ms.reduce((s, m) => s + (m.due || 0), 0);
        setDueCount(due);
        setLiveCount(ms.reduce((s, m) => s + (m.live || 0), 0));
        // Re-sync tomorrow's reminder body with the live due-count.
        void syncReviewReminder(due);
      })
      .catch(() => {/* non-fatal — just hides the review card */});
    api.getStreak()
      .then((s) => setStreak(s.streak))
      .catch(() => {/* non-fatal — keeps the local fallback */});
    api.getWeekly()
      .then(setWeekly)
      .catch(() => {/* non-fatal — just hides the week card */});
    // Re-sync the daily review reminder from the live due-set on each home open.
    void syncReviewReminder();
  }, []);

  // Profile photo, shared from the Profile page (kept in sync via the event).
  useEffect(() => {
    const load = () => setAvatar(getAvatar(user?.id));
    load();
    window.addEventListener("ee-avatar-changed", load);
    return () => window.removeEventListener("ee-avatar-changed", load);
  }, [user?.id]);

  useEffect(() => {
    const st = loc.state as { focusSearch?: number } | null;
    if (st?.focusSearch) {
      setSearchOpen(true);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc.key]);

  useEffect(() => {
    if (searchOpen && phrases === null) {
      api.listPhrases().then(setPhrases).catch(() => setPhrases([]));
    }
  }, [searchOpen, phrases]);

  const closeSearch = () => {
    setSearchOpen(false);
    setQ("");
  };

  // Library carousels: one horizontal row per direction, curated order.
  const rows = useMemo(() => {
    const bySlug: Record<string, BatchListItem[]> = {};
    for (const b of batches) (bySlug[b.section || "__other"] ||= []).push(b);
    for (const k in bySlug) bySlug[k].sort((a, c) => numOf(a.slug) - numOf(c.slug));
    const out: { slug: string; items: BatchListItem[]; nav: boolean }[] = [];
    const known = new Set<string>();
    for (const sec of orderedSections()) {
      known.add(sec.slug);
      const items = bySlug[sec.slug];
      if (items?.length) out.push({ slug: sec.slug, items, nav: true });
    }
    const other = batches
      .filter((b) => !known.has(b.section))
      .sort((a, c) => numOf(a.slug) - numOf(c.slug));
    if (other.length) out.push({ slug: "__other", items: other, nav: false });
    return out;
  }, [batches]);

  // Progress metrics — PHRASES, not batches (per request). Mastered =
  // familiar+automatic; in-work = shaky. Straight off the SRS mastery rollup.
  const phrasesMastered = useMemo(
    () => mastery.reduce((s, m) => { const r = m.srs || {}; return s + (r.familiar || 0) + (r.automatic || 0); }, 0),
    [mastery]
  );
  const phrasesInWork = useMemo(
    () => mastery.reduce((s, m) => s + ((m.srs || {}).shaky || 0), 0),
    [mastery]
  );

  // Active batches — what's in the practice-deck rotation (activated). Shown as the
  // FIRST library row (in-progress first, completed last). Long-press → menu.
  const activeRow = useMemo(
    () =>
      batches
        .filter((b) => isActive(getProgress(b.id)))
        .sort((a, c) => {
          const ac = isClosed(a.id) ? 1 : 0;
          const cc = isClosed(c.id) ? 1 : 0;
          if (ac !== cc) return ac - cc;
          return numOf(a.slug) - numOf(c.slug);
        }),
    [batches, pv]
  );

  // Current Focus = the active batch of the learner's sprint (or, if nothing
  // started, the most recent collection).
  // The home hero = the plan's active node (same order as the map), skipping
  // locked content so it never plays an empty session. pv re-reads on progress
  // change so a just-completed focus advances. See lib/plan.ts.
  const focus = useMemo(() => planFocus(batches), [batches, pv]);

  const needle = q.trim().toLowerCase();
  const allOrdered = useMemo(
    () => [...batches].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [batches]
  );
  const matchedBatches = useMemo(() => {
    if (!needle) return [];
    return allOrdered.filter((b) =>
      [b.title, b.preview, b.subtitle, b.theme, ...(b.anchors || [])]
        .filter(Boolean)
        .some((t) => t.toLowerCase().includes(needle))
    );
  }, [allOrdered, needle]);
  const matchedPhrases = useMemo(() => {
    if (!needle || !phrases) return [];
    return phrases
      .filter((p) =>
        [p.phrase_en, p.anchor, p.gloss_ru, p.batch_title]
          .filter(Boolean)
          .some((t) => t.toLowerCase().includes(needle))
      )
      .slice(0, 50);
  }, [phrases, needle]);
  const searching = searchOpen && needle.length > 0;

  const startFocus = async () => {
    if (!focus) return;
    try {
      const b = await api.getBatch(focus.id);
      // Locked batches come back with phrases:[] — never start an empty player;
      // the batch page carries the unlock CTA instead.
      if (!b.phrases.length) { nav(`/batch/${focus.id}`); return; }
      player.playBatch(b, { mode: "listening", order: "full_random" });
      nav("/play");
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="screen lib-home">
      {searchOpen ? (
        <div className="lib-search">
          <div className="search-field">
            <IconSearch size={18} />
            <input
              ref={inputRef}
              className="search-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("lib.searchPlaceholder")}
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              enterKeyHint="search"
            />
            {q && (
              <button className="search-clear" onClick={() => setQ("")} aria-label={t("lib.clearAria")}>
                ×
              </button>
            )}
          </div>
          <button className="search-cancel" onClick={closeSearch}>{t("common.cancel")}</button>
        </div>
      ) : (
        <div className="brand-head">
          <div className="brand-text">
            <h1 className="brand-title">
              <span className="brand-en">English</span>
              <span className="brand-ex">Executive</span>
            </h1>
            <p className="brand-sub">Executive communication.<br />Built for real conversations.</p>
          </div>
          <button className="avatar-btn" onClick={() => nav("/profile")} aria-label={t("common.profile")}>
            {avatar ? <img className="avatar-img" src={avatar} alt="" /> : initials}
          </button>
        </div>
      )}

      {err && <p className="error">{err}</p>}

      {!err && batches.length === 0 && (
        <div className="empty">
          <p>{t("lib.empty")}</p>
          <button className="btn btn-tint" onClick={() => nav("/import")}>
            {t("lib.importFirst")}
          </button>
        </div>
      )}

      {searching && (
        <>
          {matchedBatches.length > 0 && (
            <section>
              <p className="section-label">{t("lib.collections")} · {matchedBatches.length}</p>
              <div className="grid">
                {matchedBatches.map((b, i) => (
                  <BatchTapButton
                    key={b.id}
                    batchId={b.id}
                    title={b.title}
                    className="album"
                    style={{ animationDelay: `${i * 40}ms` }}
                  >
                    <span className="album-art">
                      <BatchCover seed={b.slug} coverUrl={b.cover_url} locked={b.locked} />
                    </span>
                    <div className="album-title">{b.title}</div>
                    {b.preview && <div className="album-sub">{b.preview}</div>}
                    <div className="album-meta">{t("lib.nPatterns", { n: b.phrase_count })}</div>
                  </BatchTapButton>
                ))}
              </div>
            </section>
          )}
          {matchedPhrases.length > 0 && (
            <section>
              <p className="section-label">{t("lib.phrases")} · {matchedPhrases.length}</p>
              <div className="srch-list">
                {matchedPhrases.map((p) => (
                  <button
                    key={p.phrase_id}
                    className="srch-phrase"
                    onClick={() => nav(`/batch/${p.batch_id}`)}
                  >
                    <div className="sp-en">{p.phrase_en}</div>
                    <div className="sp-meta">
                      <span className="sp-anchor">{p.anchor}</span> · {p.batch_title}
                    </div>
                  </button>
                ))}
              </div>
            </section>
          )}
          {matchedBatches.length === 0 && matchedPhrases.length === 0 && (
            <p className="muted" style={{ marginTop: 8 }}>
              {phrases === null ? t("lib.searchingDots") : t("lib.noResults")}
            </p>
          )}
        </>
      )}

      {!searching && batches.length > 0 && (
        <>
          {/* Progress overview — a lightweight metadata row. */}
          <div className="metrics">
            <div className="metric">
              <span className="metric-ico">
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              </span>
              <span className="metric-num">{phrasesMastered}</span>
              <span className="metric-label">{t("lib.mMastered")}</span>
            </div>
            <div className="metric">
              <span className="metric-ico">
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 17l5-6 4 4 6-8" /><path d="M18 7h3v3" />
                </svg>
              </span>
              <span className="metric-num">{phrasesInWork}</span>
              <span className="metric-label">{t("lib.mInWork")}</span>
            </div>
            <div className="metric">
              <span className="metric-ico">
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 3c.5 3-1.5 4-1.5 6.5A3.5 3.5 0 0012 13a3 3 0 003-3c1 1.5 2 3 2 5a5 5 0 11-10 0c0-3.5 3-5 5-12z" />
                </svg>
              </span>
              <span className="metric-num">{streak}</span>
              <span className="metric-label">{t("lib.mStreak")}</span>
            </div>
          </div>

          {/* Spaced repetition — a calm, opt-in refresh of phrases that are due.
              Shown only when something is actually due; no badge/streak pressure. */}
          {dueCount > 0 && (
            <button className="review-due" onClick={() => nav("/practice", { state: { review: true } })}>
              <span className="review-due-ico">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 4v4h4" />
                </svg>
              </span>
              <span className="review-due-text">
                <span className="review-due-title">{t("review.dueTitle")}</span>
                <span className="review-due-sub">{t("review.dueSub", { n: dueCount })}</span>
              </span>
              <span className="review-due-go">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
              </span>
            </button>
          )}

          {/* Moment of the day — the phrases you reached for in a real Live
              conversation, brought back to drill (Live→SRS loop made visible).
              Green accent = the Live surface it comes from. */}
          {liveCount > 0 && (
            <button className="review-due live-moment" onClick={() => nav("/practice", { state: { live: true } })}>
              <span className="review-due-ico">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" />
                </svg>
              </span>
              <span className="review-due-text">
                <span className="review-due-title">{t("live.momentTitle")}</span>
                <span className="review-due-sub">{t("live.momentSub", { n: liveCount })}</span>
              </span>
              <span className="review-due-go">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
              </span>
            </button>
          )}

          {/* League retest — once a result has gone stale (≥5 weeks), nudge a
              retake so the learner can SEE they grew. Mutually exclusive with the
              first-run entry card below (that needs no result; this needs one). */}
          {retestDue && (
            <button className="review-due league-entry" onClick={() => nav("/league")}>
              <span className="review-due-ico">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M8 21h8M12 17v4M6 3h12v6a6 6 0 01-12 0V3z" /><path d="M6 5H3v2a4 4 0 004 4M18 5h3v2a4 4 0 01-4 4" />
                </svg>
              </span>
              <span className="review-due-text">
                <span className="review-due-title">{t("league.retestTitle")}</span>
                <span className="review-due-sub">{t("league.retestSub", { n: Math.max(1, Math.round((retestDays ?? 35) / 7)) })}</span>
              </span>
              <span className="review-due-go">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
              </span>
            </button>
          )}

          {/* League test — the conversion hook, shown until taken or skipped. */}
          {!leagueHidden && (
            <button className="review-due league-entry" onClick={() => nav("/league")}>
              <span className="review-due-ico">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M8 21h8M12 17v4M6 3h12v6a6 6 0 01-12 0V3z" /><path d="M6 5H3v2a4 4 0 004 4M18 5h3v2a4 4 0 01-4 4" />
                </svg>
              </span>
              <span className="review-due-text">
                <span className="review-due-title">{t("league.entryTitle")}</span>
                <span className="review-due-sub">{t("league.entrySub")}</span>
              </span>
              <span
                className="league-skip"
                role="button"
                aria-label={t("league.skip")}
                onClick={(e) => { e.stopPropagation(); dismissLeagueCard(); setLeagueHidden(true); }}
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
              </span>
            </button>
          )}

          {/* Widget suggestion (native) — iOS can't add it for the user, so we
              suggest: tap → the how-to sheet; ✕ → never again; auto-retires once
              WidgetKit reports the widget is on the screen. */}
          {widgetNudge && (
            <button className="review-due widget-nudge" onClick={() => setWidgetHowto(true)}>
              <span className="review-due-ico">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="8" height="8" rx="2" /><rect x="13" y="3" width="8" height="8" rx="2" /><rect x="3" y="13" width="8" height="8" rx="2" /><path d="M17 14v6M14 17h6" />
                </svg>
              </span>
              <span className="review-due-text">
                <span className="review-due-title">{t("widget.nudgeTitle")}</span>
                <span className="review-due-sub">{t("widget.nudgeSub")}</span>
              </span>
              <span
                className="league-skip"
                role="button"
                aria-label={t("widget.dismiss")}
                onClick={(e) => { e.stopPropagation(); if (user?.id != null) dismissWidgetNudge(user.id); setWidgetNudge(false); }}
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
              </span>
            </button>
          )}
          {widgetHowto && <WidgetHowto onClose={() => setWidgetHowto(false)} />}

          {/* Your week — a calm progress cue: how much work landed and which
              phrases stood out. Only once the week has real substance. */}
          {weekly && weekly.attempts >= 5 && (
            <div className="week-card">
              <div className="week-head">
                <span className="week-title">{t("week.title")}</span>
                <span className="week-stats">{t("week.stats", { days: weekly.days_active, n: weekly.attempts })}</span>
              </div>
              {weekly.best.length > 0 && (
                <div className="week-list">
                  <span className="week-lbl">{t("week.best")}</span>
                  {weekly.best.slice(0, 2).map((p) => (
                    <span className="week-phrase" key={p.phrase_id}>{p.phrase_en}</span>
                  ))}
                </div>
              )}
              {weekly.focus.length > 0 && (
                <div className="week-list">
                  <span className="week-lbl">{t("week.focus")}</span>
                  {weekly.focus.slice(0, 1).map((p) => (
                    <span className="week-phrase dim" key={p.phrase_id}>{p.phrase_en}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Current Focus — the hero. */}
          {focus && (
            <>
            <p className="focus-label">{t("lib.focus")}</p>
            <div className="focus-hero" data-tour="hero">
              <span className="focus-hero-art">
                <BatchCover seed={focus.slug} coverUrl={focus.cover_url} locked={focus.locked} />
              </span>
              <span className="focus-hero-grad" />
              <span className="focus-hero-body">
                <span className="focus-hero-title">{focus.title}</span>
                {focus.preview && <span className="focus-hero-sub">{focus.preview}</span>}
                <span className="focus-hero-meta">
                  {t("lib.nPatterns", { n: focus.phrase_count })} · {Math.max(8, Math.round(focus.phrase_count * 1.5))} min
                </span>
              </span>
              <BatchTapButton className="focus-hero-open" batchId={focus.id} title={focus.title}
                ariaLabel={focus.title}>{null}</BatchTapButton>
              <button
                className="focus-hero-play"
                aria-label={t("lib.listenAria")}
                onClick={startFocus}
              >
                <IconPlay size={22} />
              </button>
            </div>
            </>
          )}

          {/* Active batches — first row: what you're studying. */}
          {activeRow.length > 0 && (
            <section className="lib-row" key="__active">
              <div className="lib-row-head">
                <span className="lib-row-title">{t("lib.active")}</span>
              </div>
              <div className="row-scroll">
                {activeRow.map((b) => (
                  <BatchTapButton key={b.id} batchId={b.id} title={b.title} className="row-card">
                    <span className="row-card-art">
                      <BatchCover seed={b.slug} coverUrl={b.cover_url} locked={b.locked} />
                      {isClosed(b.id) && <span className="row-card-done">✓</span>}
                    </span>
                    <div className="row-card-title">{b.title}</div>
                    {b.preview && <div className="row-card-sub">{b.preview}</div>}
                  </BatchTapButton>
                ))}
              </div>
            </section>
          )}

          {/* Content library — carousels per direction. */}
          {rows.map((row) => (
            <section className="lib-row" key={row.slug}>
              <button
                className="lib-row-head"
                onClick={() => row.nav && nav(`/section/${row.slug}`)}
                disabled={!row.nav}
              >
                <span className="lib-row-title">
                  {row.slug === "__other" ? t("lib.other") : sectionName(row.slug)}
                </span>
                {row.nav && (
                  <svg className="lib-row-chev" width="9" height="16" viewBox="0 0 9 16" fill="none">
                    <path d="M1 1l7 7-7 7" stroke="currentColor" strokeWidth="2"
                          strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
              <div className="row-scroll">
                {row.items.map((b) => (
                  <BatchTapButton key={b.id} batchId={b.id} title={b.title} className="row-card">
                    <span className="row-card-art">
                      <BatchCover seed={b.slug} coverUrl={b.cover_url} locked={b.locked} />
                    </span>
                    <span
                      className={`row-add${isInManual(b.id) ? " in" : ""}`}
                      role="button"
                      aria-label={isInManual(b.id) ? t("plan.removeManual") : t("plan.addManual")}
                      onPointerDown={(e) => e.stopPropagation()}
                      onPointerUp={(e) => e.stopPropagation()}
                      onTouchStart={(e) => e.stopPropagation()}
                      onClick={(e) => {
                        e.stopPropagation();
                        isInManual(b.id) ? removeManual(b.id) : addManual(b.id);
                      }}
                    >
                      {isInManual(b.id) ? "✓" : "+"}
                    </span>
                    <div className="row-card-title">{b.title}</div>
                    {b.preview && <div className="row-card-sub">{b.preview}</div>}
                  </BatchTapButton>
                ))}
              </div>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
