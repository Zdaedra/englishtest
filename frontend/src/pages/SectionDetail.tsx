import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, BatchListItem } from "../api";
import { BatchCover } from "../ui/Art";
import { IconBack } from "../ui/icons";
import { SECTION_BY_SLUG } from "../lib/sections";

const numOf = (slug: string) => {
  const m = slug.match(/(\d+)\s*$/);
  return m ? parseInt(m[1], 10) : 0;
};

export default function SectionDetail() {
  const { slug = "" } = useParams();
  const nav = useNavigate();
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.listBatches().then(setBatches).catch((e) => setErr(String(e)));
  }, []);

  const sec = SECTION_BY_SLUG[slug];
  const items = useMemo(
    () =>
      batches
        .filter((b) => b.section === slug)
        .sort((a, c) => numOf(a.slug) - numOf(c.slug)),
    [batches, slug]
  );

  return (
    <div className="screen">
      <button className="back-link" onClick={() => nav(-1)}>
        <IconBack size={18} /> Библиотека
      </button>

      <div className="screen-head">
        <h1 className="app-title">{sec?.ru || slug}</h1>
        {sec?.blurb && <p className="app-sub">{sec.blurb}</p>}
      </div>

      {err && <p className="error">{err}</p>}

      <div className="grid">
        {items.map((b, i) => (
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

      {!err && items.length === 0 && (
        <p className="muted" style={{ marginTop: 8 }}>Скоро</p>
      )}
    </div>
  );
}
