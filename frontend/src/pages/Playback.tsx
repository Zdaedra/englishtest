import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { usePlayer } from "../player/PlayerContext";
import { useI18n } from "../i18n";
import { accentFor, accentVars, fmtTime } from "../lib/accent";
import {
  IconBack, IconPlay, IconPause, IconPrev, IconNext,
  IconSpeed, IconShuffle, IconLoop, IconHeart,
} from "../ui/icons";

export default function Playback() {
  const p = usePlayer();
  const nav = useNavigate();
  const { t } = useI18n();
  const [loadingFocus, setLoadingFocus] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  // Opening the Playback tab with nothing loaded yet defaults to the current
  // focus (most-recent) batch, loaded but paused — so it never dead-ends.
  useEffect(() => {
    if (p.batch || p.busy || loadingFocus) return;
    setLoadingFocus(true);
    api
      .listBatches()
      .then((list) => {
        const focus = [...list].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
        if (!focus) return;
        return api.getBatch(focus.id).then((b) =>
          p.playBatch(b, { mode: "listening", order: "full_random", autoplay: false })
        );
      })
      .finally(() => setLoadingFocus(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.batch, p.busy]);

  if (!p.batch || (!p.session && !p.busy)) {
    if (loadingFocus) {
      return (
        <div className="screen empty">
          <p className="faint">{t("common.loading")}</p>
        </div>
      );
    }
    return (
      <div className="screen empty">
        <p>{t("pb.nothing")}</p>
        <p className="small faint">{t("pb.chooseSet")}</p>
        <button className="btn btn-tint" onClick={() => nav("/")}>
          {t("pb.goLibrary")}
        </button>
      </div>
    );
  }

  const accent = accentFor(p.batch.id);
  const phrase = p.currentOrder != null ? p.phraseByOrder.get(p.currentOrder) : undefined;
  const count = p.playSequence.length;
  // The list is ALWAYS in fixed mnemonic order; shuffle only randomises playback.
  const fixedOrder = [...p.batch.phrases].sort((a, b) => a.order_index - b.order_index);
  const idx = p.currentIndex < 0 ? 0 : p.currentIndex;
  const frac = p.duration ? Math.max(0, Math.min(1, p.t / p.duration)) : 0;
  const pct = `${frac * 100}%`;
  const fav = p.isFavorite(p.batch.id);

  const seekAtClientX = (clientX: number) => {
    const el = trackRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (r.width <= 0) return;
    p.seekFraction(Math.max(0, Math.min(1, (clientX - r.left) / r.width)));
  };

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragging(true);
    seekAtClientX(e.clientX);
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    seekAtClientX(e.clientX);
  };
  const endDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    setDragging(false);
    try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* already released */ }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!p.duration) return;
    const step = 5; // seconds per arrow press
    if (e.key === "ArrowRight" || e.key === "ArrowUp") {
      p.seekFraction(Math.min(1, (p.t + step) / p.duration)); e.preventDefault();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
      p.seekFraction(Math.max(0, (p.t - step) / p.duration)); e.preventDefault();
    } else if (e.key === "Home") {
      p.seekFraction(0); e.preventDefault();
    } else if (e.key === "End") {
      p.seekFraction(1); e.preventDefault();
    }
  };

  return (
    <div className="playback" style={accentVars(accent)}>
      <div className="pb-top">
        <button
          className="back-link pb-back"
          onClick={() => nav(p.batch ? `/batch/${p.batch.id}` : "/")}
          aria-label={t("common.back")}
        >
          <IconBack />
        </button>
        <span className="pb-batch">{p.batch.title}</span>
        <div className="seg">
          <button className={p.mode === "listening" ? "on" : ""} onClick={() => p.changeMode("listening")}>
            {t("pb.listen")}
          </button>
          <button className={p.mode === "recall" ? "on" : ""} onClick={() => p.changeMode("recall")}>
            {t("pb.recall")}
          </button>
        </div>
      </div>

      <div className="pb-hero">
        {p.busy && !p.session ? (
          <div className="pb-anchor" style={{ opacity: 0.4 }}>…</div>
        ) : (
          <>
            <div className="pb-anchor">{phrase?.anchor ?? p.batch.title}</div>
            {phrase?.phrase_en && <div className="pb-phrase">{phrase.phrase_en}</div>}
            {phrase?.gloss_ru && <div className="pb-gloss">{phrase.gloss_ru}</div>}
            {count > 0 && <div className="pb-counter">{t("pb.counter", { i: idx + 1, n: count })}</div>}
          </>
        )}
      </div>

      {p.err && <p className="error">{p.err}</p>}

      <div className="scrub">
        <div
          ref={trackRef}
          className={"scrub-hit" + (dragging ? " dragging" : "")}
          role="slider"
          tabIndex={0}
          aria-label={t("pb.seekAria")}
          aria-valuemin={0}
          aria-valuemax={Math.round(p.duration) || 0}
          aria-valuenow={Math.round(p.t) || 0}
          aria-valuetext={`${fmtTime(p.t)} / ${fmtTime(p.duration)}`}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onKeyDown={onKeyDown}
        >
          <div className="scrub-track">
            <div className="scrub-fill" style={{ width: pct }} />
          </div>
          <div className="scrub-thumb" style={{ left: pct }} />
        </div>
        <div className="scrub-time">
          <span>{fmtTime(p.t)}</span>
          <span>{fmtTime(p.duration)}</span>
        </div>
      </div>

      <div className="transport">
        <button className="tp-skip" onClick={p.prev} aria-label={t("pb.prevAria")}><IconPrev size={30} /></button>
        <button className="play-fab" onClick={p.toggle} aria-label={t("pb.playPauseAria")}>
          {p.playing ? <IconPause size={34} /> : <IconPlay size={34} />}
        </button>
        <button className="tp-skip" onClick={p.next} aria-label={t("pb.nextAria")}><IconNext size={30} /></button>
      </div>

      <div className="pb-tools">
        <button className={"tool" + (p.rate !== 1 ? " on" : "")} onClick={p.cycleRate}>
          <span className="tool-ico"><IconSpeed size={19} /></span>
          {p.rate}×
        </button>
        <button className={"tool" + (p.order === "full_random" ? " on" : "")} onClick={p.reshuffle}>
          <span className="tool-ico"><IconShuffle size={19} /></span>
          {t("pb.shuffle")}
        </button>
        <button className={"tool" + (p.loop ? " on" : "")} onClick={p.toggleLoop}>
          <span className="tool-ico"><IconLoop size={19} /></span>
          {t("pb.loop")}
        </button>
        <button className={"tool" + (fav ? " on" : "")} onClick={() => p.toggleFavorite(p.batch!.id)}>
          <span className="tool-ico"><IconHeart size={19} fill={fav} /></span>
          {t("pb.favorite")}
        </button>
      </div>

      {fixedOrder.length > 0 && (
        <div className="pattern-list">
          {fixedOrder.map((ph, i) => {
            const cur = ph.order_index === p.currentOrder;
            return (
              <button
                key={ph.id}
                className={"pattern-row" + (cur ? " cur" : "")}
                onClick={() => p.goToOrder(ph.order_index)}
              >
                <span className="pr-mark">{cur ? <IconPlay size={13} /> : i + 1}</span>
                <div className="pr-body">
                  <div className="pr-anchor">{ph.anchor}</div>
                  <div className="pr-phrase">{ph.phrase_en}</div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
