import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, BatchDetail as Batch, RotationItem } from "../api";
import { usePlayer } from "../player/PlayerContext";
import { getProgress, lessonStates, LessonState } from "../lib/progress";
import { BatchCover } from "../ui/Art";
import { IconBack, IconCheck, IconChevron } from "../ui/icons";

function firstSentence(s: string): string {
  const t = (s || "").trim();
  if (!t) return "";
  return t.split(/(?<=[.!?…])\s/)[0].trim();
}

const LESSONS = [
  { n: 1, title: "Мнемоническая основа", sub: "Запомни каркас якорей" },
  { n: 2, title: "Фразы", sub: "Привяжи фразы к якорям" },
  { n: 3, title: "Тесты", sub: "Проверь на скорость" },
];

export default function BatchHome() {
  const { id } = useParams();
  const nav = useNavigate();
  const player = usePlayer();
  const [batch, setBatch] = useState<Batch | null>(null);
  const [rotation, setRotation] = useState<RotationItem[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!id) return;
    api.getBatch(Number(id)).then(setBatch).catch((e) => setErr(String(e)));
    api.getRotation(Number(id)).then(setRotation).catch(() => {});
  }, [id]);

  // Warm phrase clips so the first tap-to-hear inside a lesson is instant.
  useEffect(() => {
    if (batch) player.prefetchPhrases(batch.phrases.map((p) => p.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch]);

  const ordered = useMemo(
    () => (batch ? [...batch.phrases].sort((a, b) => a.order_index - b.order_index) : []),
    [batch]
  );

  // Lesson 2 progress is derived live from the rotation (avg_score / attempts).
  const l2 = useMemo(() => {
    if (!rotation || rotation.length === 0) return { attempted: 0, total: 0, mean: 0, done: false };
    const attempted = rotation.filter((r) => r.attempts > 0);
    const scored = attempted.filter((r) => r.avg_score != null);
    const mean = scored.length
      ? scored.reduce((s, r) => s + (r.avg_score as number), 0) / scored.length
      : 0;
    const done = attempted.length === rotation.length && mean >= 6;
    return { attempted: attempted.length, total: rotation.length, mean, done };
  }, [rotation]);

  if (err) return <div className="screen"><p className="error">{err}</p></div>;
  if (!batch) return <div className="screen"><p className="muted">Loading…</p></div>;

  const preview = batch.subtitle?.trim() || firstSentence(batch.mnemo?.story_ru || "");
  const prog = getProgress(batch.id);
  const states = lessonStates(prog, l2.done);

  const badge = (n: number, st: LessonState) => {
    if (st === "done") return <span className="lc-badge done"><IconCheck size={14} /></span>;
    if (n === 2 && l2.attempted > 0)
      return <span className="lc-badge">{l2.attempted}/{l2.total}</span>;
    return <span className="lc-badge"><IconChevron size={16} /></span>;
  };

  return (
    <div className="screen">
      <button className="back-link" onClick={() => nav(-1)}>
        <IconBack /> Назад
      </button>

      <span className="detail-art">
        <BatchCover seed={batch.slug} coverUrl={batch.cover_url} />
      </span>

      <div className="detail-head">
        <div className="detail-title">{batch.title}</div>
        {preview && <div className="detail-sub">{preview}</div>}
      </div>

      <div className="mnemo-seq static">
        {ordered.map((p, i) => (
          <span key={p.id} className="anchor-wrap">
            {i > 0 && <span className="seq-arrow">→ </span>}
            <span className="seq-anchor">{p.anchor}</span>
          </span>
        ))}
      </div>

      <p className="section-label" style={{ marginTop: 26 }}>Уроки</p>
      <div className="lesson-ladder">
        {LESSONS.map((l, i) => {
          const st = states[i];
          return (
            <button
              key={l.n}
              className={`lesson-card ${st}`}
              onClick={() => nav(`/batch/${batch.id}/lesson/${l.n}`)}
            >
              <span className="lc-num">{st === "done" ? <IconCheck size={18} /> : l.n}</span>
              <span className="lc-body">
                <span className="lc-title">{l.title}</span>
                <span className="lc-sub">
                  {l.n === 2 && l2.attempted > 0 && !l2.done
                    ? `${l.sub} · средний ${l2.mean.toFixed(1)}`
                    : l.sub}
                </span>
              </span>
              {badge(l.n, st)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
