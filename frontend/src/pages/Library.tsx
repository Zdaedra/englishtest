import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, BatchListItem, PhraseSearchItem } from "../api";
import { BatchCover } from "../ui/Art";
import { IconSearch } from "../ui/icons";
import { orderedSections } from "../lib/sections";

// Natural order inside a direction: charisma-1, charisma-2, … charisma-11.
const numOf = (slug: string) => {
  const m = slug.match(/(\d+)\s*$/);
  return m ? parseInt(m[1], 10) : 0;
};

export default function Library() {
  const nav = useNavigate();
  const loc = useLocation();
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [err, setErr] = useState("");

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

  // Group batches into the section rows (Apple-Music browse: each direction is a
  // horizontal carousel, directions stacked top→bottom in the curated order).
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

  return (
    <div className="screen">
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
        <div className="screen-head lib-head">
          <div className="lib-head-text">
            <h1 className="app-title">English Executive</h1>
            <p className="app-sub">Executive communication. Built for real conversations.</p>
          </div>
          <button className="avatar-btn" onClick={() => nav("/profile")} aria-label="Profile">
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
              <p className="section-label">Батчи · {matchedBatches.length}</p>
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

      {!searching &&
        rows.map((row) => (
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
    </div>
  );
}
