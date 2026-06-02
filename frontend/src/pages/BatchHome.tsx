import { Fragment, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, BatchDetail as Batch, BatchListItem, RotationItem } from "../api";
import { usePlayer } from "../player/PlayerContext";
import { getProgress, lessonStates } from "../lib/progress";
import { orderedSections } from "../lib/sections";
import { getProfile, prioritySectionSlugs } from "../lib/profile";
import { BatchCover } from "../ui/Art";
import { IconBack, IconCheck, IconChevron, IconHeadphones, IconPlay } from "../ui/icons";

function firstSentence(s: string): string {
  const t = (s || "").trim();
  if (!t) return "";
  return t.split(/(?<=[.!?…])\s/)[0].trim();
}

const LESSONS = [
  { n: 1, title: "Мнемоническая основа", sub: "Запомни каркас якорей", cta: "урок" },
  { n: 2, title: "Фразы", sub: "Привяжи фразы к якорям", cta: "фразы" },
  { n: 3, title: "Тесты", sub: "Проверь на скорость", cta: "тесты" },
];

export default function BatchHome() {
  const { id } = useParams();
  const nav = useNavigate();
  const player = usePlayer();
  const [batch, setBatch] = useState<Batch | null>(null);
  const [rotation, setRotation] = useState<RotationItem[] | null>(null);
  const [batchList, setBatchList] = useState<BatchListItem[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!id) return;
    api.getBatch(Number(id)).then(setBatch).catch((e) => setErr(String(e)));
    api.getRotation(Number(id)).then(setRotation).catch(() => {});
    api.listBatches().then(setBatchList).catch(() => {});
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

  // The batch's 1-based position in the learning path (same flatten as the map:
  // sections by the learner's priority, batches oldest-first within a section).
  const lessonNum = useMemo(() => {
    if (!batch || !batchList) return 0;
    const bySection = new Map<string, BatchListItem[]>();
    batchList.forEach((b) => {
      const k = b.section || "_";
      const arr = bySection.get(k);
      if (arr) arr.push(b);
      else bySection.set(k, [b]);
    });
    const natural = orderedSections().map((s) => s.slug);
    const order = prioritySectionSlugs(getProfile(), natural);
    const flat: BatchListItem[] = [];
    order.forEach((slug) =>
      flat.push(...(bySection.get(slug) ?? []).sort((a, b) => a.created_at.localeCompare(b.created_at)))
    );
    const seen = new Set(flat.map((b) => b.id));
    batchList
      .filter((b) => !seen.has(b.id))
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
      .forEach((b) => flat.push(b));
    const idx = flat.findIndex((b) => b.id === batch.id);
    return idx >= 0 ? idx + 1 : 0;
  }, [batch, batchList]);

  if (err) return <div className="screen"><p className="error">{err}</p></div>;
  if (!batch) return <div className="screen"><p className="muted">Loading…</p></div>;

  const preview = batch.subtitle?.trim() || firstSentence(batch.mnemo?.story_ru || "");
  const states = lessonStates(getProgress(batch.id), l2.done);
  const openIdx = states.findIndex((s) => s === "open");
  const allDone = states.every((s) => s === "done");
  const activeIdx = openIdx >= 0 ? openIdx : 2; // all done → review the tests
  const ctaLesson = LESSONS[activeIdx];

  return (
    <div className="screen bh-screen">
      <button className="bh-back" onClick={() => nav(-1)}>
        <IconBack size={18} /> Назад
      </button>

      <span className="bh-cover">
        <BatchCover seed={batch.slug} coverUrl={batch.cover_url} />
      </span>

      <div className="bh-head">
        {lessonNum > 0 && <span className="bh-tag">Урок {lessonNum}</span>}
        <h1 className="bh-title">{batch.title}</h1>
        {preview && <p className="bh-sub">{preview}</p>}
      </div>

      <div className="bh-anchors">
        {ordered.map((p, i) => (
          <Fragment key={p.id}>
            {i > 0 && <span className="bh-arrow">→</span>}
            <span className="bh-anchor">{p.anchor}</span>
          </Fragment>
        ))}
      </div>

      <p className="bh-steps-label">Этапы урока</p>
      <div className="bh-lessons">
        {LESSONS.map((l, i) => {
          const st = states[i];
          const done = st === "done";
          const active = st === "open";
          return (
            <button
              key={l.n}
              className={`bh-lesson${done ? " done" : ""}${active ? " active" : ""}${st === "locked" ? " locked" : ""}`}
              onClick={() => nav(`/batch/${batch.id}/lesson/${l.n}`)}
            >
              <span className="bh-lesson-num">{done ? <IconCheck size={18} /> : l.n}</span>
              <span className="bh-lesson-body">
                <span className="bh-lesson-title">{l.title}</span>
                <span className="bh-lesson-sub">
                  {l.n === 2 && l2.attempted > 0 && !l2.done
                    ? `${l.sub} · средний ${l2.mean.toFixed(1)}`
                    : l.sub}
                </span>
              </span>
              <IconChevron size={18} />
            </button>
          );
        })}
      </div>

      <button
        className="l3-cta"
        style={{ marginTop: 22 }}
        onClick={() => nav(`/batch/${batch.id}/lesson/${ctaLesson.n}`)}
      >
        <IconPlay size={18} /> {allDone ? "Повторить" : "Начать"} {ctaLesson.cta}
      </button>
      <p className="l3-hint">
        <IconHeadphones size={15} /> Рекомендуется использовать наушники и тихое помещение
      </p>
    </div>
  );
}
