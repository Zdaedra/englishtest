import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, BatchListItem } from "../api";
import { usePlayer } from "../player/PlayerContext";
import { BatchCover } from "../ui/Art";
import { IconPlay } from "../ui/icons";

export default function Library() {
  const nav = useNavigate();
  const player = usePlayer();
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.listBatches().then(setBatches).catch((e) => setErr(String(e)));
  }, []);

  // Most-recent batch is the featured focus; all batches form the library.
  const ordered = useMemo(
    () => [...batches].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [batches]
  );
  const focus = ordered[0];

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
      <div className="screen-head lib-head">
        <div className="lib-head-text">
          <h1 className="app-title">English Executive</h1>
          <p className="app-sub">Executive communication. Built for real conversations.</p>
        </div>
        <button className="avatar-btn" onClick={() => nav("/profile")} aria-label="Profile">
          AV
        </button>
      </div>

      {err && <p className="error">{err}</p>}

      {!err && batches.length === 0 && (
        <div className="empty">
          <p>Your library is empty.</p>
          <button className="btn btn-tint" onClick={() => nav("/import")}>
            Import your first batch
          </button>
        </div>
      )}

      {focus && (
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

      {ordered.length > 0 && (
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
