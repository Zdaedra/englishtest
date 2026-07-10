import { Fragment, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, BatchDetail as Batch, BatchListItem, RotationItem } from "../api";
import { usePlayer } from "../player/PlayerContext";
import { getProgress, isEngaged, lessonStates, setProgress } from "../lib/progress";
import { planPosition } from "../lib/plan";
import { useI18n } from "../i18n";
import { haptic } from "../lib/session";
import { BatchCover } from "../ui/Art";
import { IconBack, IconCheck, IconChevron, IconHeadphones, IconPlay, IconLock } from "../ui/icons";

function firstSentence(s: string): string {
  const t = (s || "").trim();
  if (!t) return "";
  return t.split(/(?<=[.!?…])\s/)[0].trim();
}

const LESSONS = [{ n: 1 }, { n: 2 }, { n: 3 }];

export default function BatchHome() {
  const { id } = useParams();
  const nav = useNavigate();
  const { t } = useI18n();
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

  // The batch's 1-based position in the learning path — the SAME canonical order
  // as the map spine and the home focus (lib/plan.ts), so "Урок N" matches where
  // the node actually sits (incl. manual mode + path_rank reorders).
  const lessonNum = useMemo(() => {
    if (!batch || !batchList) return 0;
    return planPosition(batchList, batch.id);
  }, [batch, batchList]);

  if (err) return <div className="screen"><p className="error">{err}</p></div>;
  if (!batch) return <div className="screen"><p className="muted">{t("common.loading")}</p></div>;

  // Freemium paywall: locked (paid) batch → show an upsell instead of content.
  if (batch.locked) {
    return (
      <div className="screen bh-screen">
        <button className="bh-back" onClick={() => nav("/")}><IconBack size={18} /> {t("common.back")}</button>
        <span className="bh-cover bh-cover-locked">
          <BatchCover seed={batch.slug} coverUrl={batch.cover_url} />
          <span className="bh-lock-badge"><IconLock size={22} /></span>
        </span>
        <div className="bh-head">
          <h1 className="bh-title">{batch.title}</h1>
          <p className="bh-sub">{t("paywall.body")}</p>
        </div>
        <button className="bh-activate" onClick={() => nav("/subscribe")}>{t("paywall.cta")}</button>
      </div>
    );
  }

  const preview = batch.subtitle?.trim() || firstSentence(batch.mnemo?.story_ru || "");
  const prog = getProgress(batch.id);
  const states = lessonStates(prog, l2.done);
  const openIdx = states.findIndex((s) => s === "open");
  const allDone = states.every((s) => s === "done");
  const activeIdx = openIdx >= 0 ? openIdx : 2; // all done → review the tests
  const ctaLesson = LESSONS[activeIdx];
  const started = isEngaged(prog);
  const ctaLabel = allDone ? t("bh.repeat") : started ? t("bh.continue") : t("bh.activate");

  // Activate the batch (mark it an active batch → In Progress + Library active
  // row) and jump straight into the next open lesson.
  const activate = () => {
    haptic("medium");
    if (!prog.activated) {
      // Server stamps activated_at authoritatively; the client never read its own
      // copy, so don't write a local activatedAt (dead write, removed 2026-07-09).
      setProgress(batch.id, { activated: true });
    }
    nav(`/batch/${batch.id}/lesson/${ctaLesson.n}`);
  };

  return (
    <div className="screen bh-screen">
      <button className="bh-back" onClick={() => nav("/")}>
        <IconBack size={18} /> {t("common.back")}
      </button>

      <span className="bh-cover">
        <BatchCover seed={batch.slug} coverUrl={batch.cover_url} />
      </span>

      <div className="bh-head">
        {lessonNum > 0 && <span className="bh-tag">{t("lesson.tag", { n: lessonNum })}</span>}
        <h1 className="bh-title">{batch.title}</h1>
        {preview && <p className="bh-sub">{preview}</p>}
      </div>

      <button className="bh-activate" onClick={activate}>
        <IconPlay size={18} /> {ctaLabel}
      </button>
      <p className="l3-hint">
        <IconHeadphones size={15} /> {t("common.headphones")}
      </p>

      <div className="bh-anchors">
        {ordered.map((p, i) => (
          <Fragment key={p.id}>
            {i > 0 && <span className="bh-arrow">→</span>}
            <span className="bh-anchor">{p.anchor}</span>
          </Fragment>
        ))}
      </div>

      <p className="bh-steps-label">{t("bh.stages")}</p>
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
                <span className="bh-lesson-title">{t(`bh.l${l.n}.title`)}</span>
                <span className="bh-lesson-sub">
                  {l.n === 2 && l2.attempted > 0 && !l2.done
                    ? `${t("bh.l2.sub")} · ${t("common.meanShort", { x: l2.mean.toFixed(1) })}`
                    : t(`bh.l${l.n}.sub`)}
                </span>
              </span>
              <IconChevron size={18} />
            </button>
          );
        })}
      </div>

    </div>
  );
}
