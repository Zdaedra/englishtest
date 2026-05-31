import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { usePlayer } from "../player/PlayerContext";
import { accentFor, accentVars, fmtTime } from "../lib/accent";
import {
  IconBack, IconPlay, IconPause, IconPrev, IconNext,
  IconSpeed, IconShuffle, IconLoop, IconHeart,
} from "../ui/icons";

export default function Playback() {
  const p = usePlayer();
  const nav = useNavigate();
  const [loadingFocus, setLoadingFocus] = useState(false);

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
          <p className="faint">Loading…</p>
        </div>
      );
    }
    return (
      <div className="screen empty">
        <p>Nothing playing.</p>
        <p className="small faint">Choose a pattern set from your Library.</p>
        <button className="btn btn-tint" onClick={() => nav("/")}>
          Go to Library
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
  const pct = p.duration ? `${(p.t / p.duration) * 100}%` : "0%";
  const fav = p.isFavorite(p.batch.id);

  const onScrub = (e: React.MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    p.seekFraction((e.clientX - r.left) / r.width);
  };

  return (
    <div className="playback" style={accentVars(accent)}>
      <div className="pb-top">
        <button
          className="back-link pb-back"
          onClick={() => nav(p.batch ? `/batch/${p.batch.id}` : "/")}
          aria-label="Back"
        >
          <IconBack />
        </button>
        <span className="pb-batch">{p.batch.title}</span>
        <div className="seg">
          <button className={p.mode === "listening" ? "on" : ""} onClick={() => p.changeMode("listening")}>
            Listen
          </button>
          <button className={p.mode === "recall" ? "on" : ""} onClick={() => p.changeMode("recall")}>
            Recall
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
            {count > 0 && <div className="pb-counter">{idx + 1} OF {count}</div>}
          </>
        )}
      </div>

      {p.err && <p className="error">{p.err}</p>}

      <div className="scrub">
        <div className="scrub-track" onClick={onScrub}>
          <div className="scrub-fill" style={{ width: pct }} />
        </div>
        <div className="scrub-time">
          <span>{fmtTime(p.t)}</span>
          <span>{fmtTime(p.duration)}</span>
        </div>
      </div>

      <div className="transport">
        <button className="tp-skip" onClick={p.prev} aria-label="Previous"><IconPrev size={30} /></button>
        <button className="play-fab" onClick={p.toggle} aria-label="Play/Pause">
          {p.playing ? <IconPause size={34} /> : <IconPlay size={34} />}
        </button>
        <button className="tp-skip" onClick={p.next} aria-label="Next"><IconNext size={30} /></button>
      </div>

      <div className="pb-tools">
        <button className={"tool" + (p.rate !== 1 ? " on" : "")} onClick={p.cycleRate}>
          <span className="tool-ico"><IconSpeed size={19} /></span>
          {p.rate}×
        </button>
        <button className={"tool" + (p.order === "full_random" ? " on" : "")} onClick={p.reshuffle}>
          <span className="tool-ico"><IconShuffle size={19} /></span>
          Shuffle
        </button>
        <button className={"tool" + (p.loop ? " on" : "")} onClick={p.toggleLoop}>
          <span className="tool-ico"><IconLoop size={19} /></span>
          Loop
        </button>
        <button className={"tool" + (fav ? " on" : "")} onClick={() => p.toggleFavorite(p.batch!.id)}>
          <span className="tool-ico"><IconHeart size={19} fill={fav} /></span>
          Favorite
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
