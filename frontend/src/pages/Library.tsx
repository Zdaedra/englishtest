import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, BatchListItem, PhraseSearchItem } from "../api";
import { usePlayer } from "../player/PlayerContext";
import { BatchCover } from "../ui/Art";
import { IconPlay, IconSearch } from "../ui/icons";

export default function Library() {
  const nav = useNavigate();
  const loc = useLocation();
  const player = usePlayer();
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [err, setErr] = useState("");

  // Search (opened from the floating nav's search button).
  const [searchOpen, setSearchOpen] = useState(false);
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  // Per-phrase index for the second search block — fetched lazily on first open.
  const [phrases, setPhrases] = useState<PhraseSearchItem[] | null>(null);

  useEffect(() => {
    api.listBatches().then(setBatches).catch((e) => setErr(String(e)));
  }, []);

  // The nav's search button navigates here with a fresh focusSearch token; open
  // the field and focus it. Keyed on loc.key so a repeated tap re-triggers.
  useEffect(() => {
    const st = loc.state as { focusSearch?: number } | null;
    if (st?.focusSearch) {
      setSearchOpen(true);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc.key]);

  // Pull the phrase index the first time search opens (cheap, single request).
  useEffect(() => {
    if (searchOpen && phrases === null) {
      api.listPhrases().then(setPhrases).catch(() => setPhrases([]));
    }
  }, [searchOpen, phrases]);

  const closeSearch = () => {
    setSearchOpen(false);
    setQ("");
  };

  // Most-recent batch is the featured focus; all batches form the library.
  const ordered = useMemo(
    () => [...batches].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [batches]
  );
  const focus = ordered[0];

  const needle = q.trim().toLowerCase();
  const matchedBatches = useMemo(() => {
    if (!needle) return ordered;
    return ordered.filter((b) =>
      [b.title, b.preview, b.subtitle, b.theme, ...(b.anchors || [])]
        .filter(Boolean)
        .some((t) => t.toLowerCase().includes(needle))
    );
  }, [ordered, needle]);
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

  const startBatch = async (id: number) => {
    try {
      const b = await api.getBatch(id);
      player.playBatch(b, { mode: "listening", order: "full_random" });
      nav("/play");
    } catch (e) {
      setErr(String(e));
    }
  };

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

      {!searching && focus && (
        <section>
          <p className="section-label">Current focus</p>
          <button className="feature" onClick={() => nav(`/batch/${focus.id}`)}>
            <span className="feature-art">
              <BatchCover seed={focus.slug} coverUrl={focus.cover_url} />
            </span>
            <div className="feature-body">
              <div className="feature-title">{focus.title}</div>
              {focus.preview && <div className="feature-sub">{focus.preview}</div>}
              <div className="feature-meta">{focus.phrase_count} patterns</div>
            </div>
            <span
              className="feature-play"
              onClick={(e) => {
                e.stopPropagation();
                startBatch(focus.id);
              }}
            >
              <IconPlay size={20} />
            </span>
          </button>
        </section>
      )}

      {!searching && ordered.length > 0 && (
        <section>
          <p className="section-label">Library</p>
          <div className="grid">
            {ordered.map((b, i) => (
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
    </div>
  );
}
