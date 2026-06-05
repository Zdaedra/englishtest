import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, BatchListItem, PhraseSearchItem } from "../api";
import { usePlayer } from "../player/PlayerContext";
import { BatchCover } from "../ui/Art";
import { IconSearch, IconPlay } from "../ui/icons";
import { orderedSections } from "../lib/sections";
import { buildSprint } from "../lib/strategy";
import { getProgress, isEngaged } from "../lib/progress";
import { getStrategy, recordVisit } from "../lib/profile";

const numOf = (slug: string) => {
  const m = slug.match(/(\d+)\s*$/);
  return m ? parseInt(m[1], 10) : 0;
};
const isClosed = (id: number) => !!getProgress(id).l3_passed;

export default function Library() {
  const nav = useNavigate();
  const loc = useLocation();
  const player = usePlayer();
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [err, setErr] = useState("");
  const [streak] = useState(() => recordVisit());

  // Search (opened from the floating nav's search button).
  const [searchOpen, setSearchOpen] = useState(false);
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const [phrases, setPhrases] = useState<PhraseSearchItem[] | null>(null);

  useEffect(() => {
    api.listBatches().then(setBatches).catch((e) => setErr(String(e)));
  }, []);

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
    const out: { slug: string; title: string; items: BatchListItem[]; nav: boolean }[] = [];
    const known = new Set<string>();
    for (const sec of orderedSections()) {
      known.add(sec.slug);
      const items = bySlug[sec.slug];
      if (items?.length) out.push({ slug: sec.slug, title: sec.ru, items, nav: true });
    }
    const other = batches
      .filter((b) => !known.has(b.section))
      .sort((a, c) => numOf(a.slug) - numOf(c.slug));
    if (other.length) out.push({ slug: "__other", title: "Другое", items: other, nav: false });
    return out;
  }, [batches]);

  // Progress metrics (lightweight metadata, real data).
  const totalPatterns = useMemo(
    () => batches.reduce((s, b) => s + (b.phrase_count || 0), 0),
    [batches]
  );
  const inProgress = useMemo(
    () => batches.filter((b) => {
      const p = getProgress(b.id);
      return !p.l3_passed && isEngaged(p);
    }).length,
    [batches]
  );

  // Active batches — what the learner has activated / started / finished. Shown
  // as the FIRST library row (in-progress first, completed last).
  const activeRow = useMemo(
    () =>
      batches
        .filter((b) => isEngaged(getProgress(b.id)))
        .sort((a, c) => {
          const ac = isClosed(a.id) ? 1 : 0;
          const cc = isClosed(c.id) ? 1 : 0;
          if (ac !== cc) return ac - cc;
          return numOf(a.slug) - numOf(c.slug);
        }),
    [batches]
  );

  // Current Focus = the active batch of the learner's sprint (or, if nothing
  // started, the most recent collection).
  const focus = useMemo(() => {
    if (!batches.length) return undefined;
    const sprint = buildSprint(getStrategy(), batches, isClosed);
    if (sprint[0]) return sprint[0];
    return [...batches].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  }, [batches]);

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
              placeholder="Поиск по библиотеке"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              enterKeyHint="search"
            />
            {q && (
              <button className="search-clear" onClick={() => setQ("")} aria-label="Очистить">
                ×
              </button>
            )}
          </div>
          <button className="search-cancel" onClick={closeSearch}>Отмена</button>
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
          <button className="avatar-btn" onClick={() => nav("/profile")} aria-label="Профиль">
            AV
          </button>
        </div>
      )}

      {err && <p className="error">{err}</p>}

      {!err && batches.length === 0 && (
        <div className="empty">
          <p>Your library is empty.</p>
          <button className="btn btn-tint" onClick={() => nav("/import")}>
            Import your first batch
          </button>
        </div>
      )}

      {searching && (
        <>
          {matchedBatches.length > 0 && (
            <section>
              <p className="section-label">Коллекции · {matchedBatches.length}</p>
              <div className="grid">
                {matchedBatches.map((b, i) => (
                  <button
                    key={b.id}
                    className="album"
                    style={{ animationDelay: `${i * 40}ms` }}
                    onClick={() => nav(`/batch/${b.id}`)}
                  >
                    <span className="album-art">
                      <BatchCover seed={b.slug} coverUrl={b.cover_url} />
                    </span>
                    <div className="album-title">{b.title}</div>
                    {b.preview && <div className="album-sub">{b.preview}</div>}
                    <div className="album-meta">{b.phrase_count} patterns</div>
                  </button>
                ))}
              </div>
            </section>
          )}
          {matchedPhrases.length > 0 && (
            <section>
              <p className="section-label">Фразы · {matchedPhrases.length}</p>
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
              {phrases === null ? "Ищу…" : "Ничего не найдено"}
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
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M4 9v6M8 5v14M12 8v8M16 4v16M20 10v4" />
                </svg>
              </span>
              <span className="metric-num">{totalPatterns}</span>
              <span className="metric-label">Patterns</span>
            </div>
            <div className="metric">
              <span className="metric-ico">
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 17l5-6 4 4 6-8" /><path d="M18 7h3v3" />
                </svg>
              </span>
              <span className="metric-num">{inProgress}</span>
              <span className="metric-label">In Progress</span>
            </div>
            <div className="metric">
              <span className="metric-ico">
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 3c.5 3-1.5 4-1.5 6.5A3.5 3.5 0 0012 13a3 3 0 003-3c1 1.5 2 3 2 5a5 5 0 11-10 0c0-3.5 3-5 5-12z" />
                </svg>
              </span>
              <span className="metric-num">{streak}</span>
              <span className="metric-label">Day Streak</span>
            </div>
          </div>

          {/* Current Focus — the hero. */}
          {focus && (
            <>
            <p className="focus-label">Current Focus</p>
            <button className="focus-hero" onClick={() => nav(`/batch/${focus.id}`)}>
              <span className="focus-hero-art">
                <BatchCover seed={focus.slug} coverUrl={focus.cover_url} />
              </span>
              <span className="focus-hero-grad" />
              <span className="focus-hero-body">
                <span className="focus-hero-title">{focus.title}</span>
                {focus.preview && <span className="focus-hero-sub">{focus.preview}</span>}
                <span className="focus-hero-meta">
                  {focus.phrase_count} patterns · {Math.max(8, Math.round(focus.phrase_count * 1.5))} min
                </span>
              </span>
              <span
                className="focus-hero-play"
                role="button"
                aria-label="Слушать"
                onClick={(e) => {
                  e.stopPropagation();
                  startFocus();
                }}
              >
                <IconPlay size={22} />
              </span>
            </button>
            </>
          )}

          {/* Active batches — first row: what you're studying. */}
          {activeRow.length > 0 && (
            <section className="lib-row" key="__active">
              <div className="lib-row-head">
                <span className="lib-row-title">Активные</span>
              </div>
              <div className="row-scroll">
                {activeRow.map((b) => (
                  <button key={b.id} className="row-card" onClick={() => nav(`/batch/${b.id}`)}>
                    <span className="row-card-art">
                      <BatchCover seed={b.slug} coverUrl={b.cover_url} />
                      {isClosed(b.id) && <span className="row-card-done">✓</span>}
                    </span>
                    <div className="row-card-title">{b.title}</div>
                    {b.preview && <div className="row-card-sub">{b.preview}</div>}
                  </button>
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
                <span className="lib-row-title">{row.title}</span>
                {row.nav && (
                  <svg className="lib-row-chev" width="9" height="16" viewBox="0 0 9 16" fill="none">
                    <path d="M1 1l7 7-7 7" stroke="currentColor" strokeWidth="2"
                          strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
              <div className="row-scroll">
                {row.items.map((b) => (
                  <button key={b.id} className="row-card" onClick={() => nav(`/batch/${b.id}`)}>
                    <span className="row-card-art">
                      <BatchCover seed={b.slug} coverUrl={b.cover_url} />
                    </span>
                    <div className="row-card-title">{b.title}</div>
                    {b.preview && <div className="row-card-sub">{b.preview}</div>}
                  </button>
                ))}
              </div>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
