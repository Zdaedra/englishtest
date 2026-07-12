import { useState } from "react";
import { api } from "../api";
import { runBatchAction } from "../lib/batchActions";
import heroProblem from "../assets/onboarding-problem.png";
import heroRoute from "../assets/onboarding-route.png";
import heroBrain from "../assets/onboarding-brain.png";
import pBartlett from "../assets/why-bartlett.png";
import pMiller from "../assets/why-miller.png";
import whyMountain from "../assets/why-mountain.png";
import heroMethod from "../assets/onboarding-method.png";
import { useI18n } from "../i18n";
import LangSwitcher from "../ui/LangSwitcher";

const SLIDES = [
  { kind: "problem" },
  { kind: "why" },
  { kind: "method" },
  { kind: "gender" },
] as const;

// Thin-stroke inline icons (match the app's icon language).
const sIco = { width: 26, height: 26, viewBox: "0 0 24 24", fill: "none" } as const;
const stroke = { stroke: "currentColor", strokeWidth: 1.75, strokeLinecap: "round", strokeLinejoin: "round" } as const;
const IconStack = () => (<svg {...sIco}><g {...stroke}><path d="M12 3 21 7.5 12 12 3 7.5 12 3Z" /><path d="M3 12l9 4.5L21 12M3 16.5 12 21l9-4.5" /></g></svg>);
const IconClock = () => (<svg {...sIco}><g {...stroke}><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></g></svg>);
const IconArrow = () => (<svg {...sIco}><g {...stroke}><path d="M5 12h13M13 6l6 6-6 6" /></g></svg>);
// Evidence-row icons
const i2 = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none" } as const;
const IconScholar = () => (<svg {...i2}><g {...stroke}><circle cx="12" cy="8" r="3.6" /><path d="M5.5 20a6.5 6.5 0 0 1 13 0" /></g></svg>);
const IconColumn = () => (<svg {...i2}><g {...stroke}><path d="M4 8.5 12 4l8 4.5M5 9v8M9.5 9v8M14.5 9v8M19 9v8M3.5 20.5h17" /></g></svg>);
const IconBadge = () => (<svg {...i2}><g {...stroke}><path d="M12 3 5.5 5.5v5c0 4 3 6.4 6.5 7.5 3.5-1.1 6.5-3.5 6.5-7.5v-5L12 3Z" /><path d="M9.3 11.2 11 13l3.7-3.8" /></g></svg>);
const IconBook = () => (<svg {...i2}><g {...stroke}><path d="M12 5.5V20M12 5.5C10.5 4.3 8.4 4 4.5 4.2V18c3.9-.2 6 .1 7.5 1.3M12 5.5c1.5-1.2 3.6-1.5 7.5-1.3V18c-3.9-.2-6 .1-7.5 1.3" /></g></svg>);
const IconPin = () => (<svg {...i2}><g {...stroke}><path d="M12 21s6-5.2 6-10a6 6 0 1 0-12 0c0 4.8 6 10 6 10Z" /><circle cx="12" cy="11" r="2.2" /></g></svg>);
const IconChunks = () => (<svg {...i2}><g {...stroke}><rect x="4" y="4" width="7" height="7" rx="1.8" /><rect x="13" y="4" width="7" height="7" rx="1.8" /><rect x="4" y="13" width="7" height="7" rx="1.8" /><rect x="13" y="13" width="7" height="7" rx="1.8" /></g></svg>);
const IconChecklist = () => (<svg {...i2}><g {...stroke}><path d="M9.5 6H20M9.5 12H20M9.5 18H20M3.5 6l1.3 1.3L7.2 5M3.5 12l1.3 1.3L7.2 11M3.5 18l1.3 1.3L7.2 17" /></g></svg>);
const IconBulb = () => (<svg {...i2}><g {...stroke}><path d="M9.5 18.5h5M10.5 21.5h3" /><path d="M12 2.8a6 6 0 0 0-3.6 10.8c.6.5 1.1 1.2 1.1 2h5c0-.8.5-1.5 1.1-2A6 6 0 0 0 12 2.8Z" /></g></svg>);
const IconTemple = () => (<svg {...i2}><g {...stroke}><path d="M4 9 12 4l8 5M4 9h16M5.5 9v9M9 9v9M15 9v9M18.5 9v9M3.5 18.5h17M3.5 21h17" /></g></svg>);
const IconWings = () => (<svg {...i2}><g {...stroke}><circle cx="12" cy="7" r="2.4" /><path d="M12 9.2v3M9.6 12.2h4.8" /><path d="M9 13.5c-2.4 0-4.5 .9-6 2.2 1.8.5 3.6.6 6 .3M15 13.5c2.4 0 4.5.9 6 2.2-1.8.5-3.6.6-6 .3" /></g></svg>);

// Method-slide icons
const mIco = { width: 22, height: 22, viewBox: "0 0 24 24", fill: "none" } as const;
const IconMagnifier = () => (<svg {...mIco}><g {...stroke}><circle cx="10.5" cy="10.5" r="5.5" /><path d="m14.5 14.5 5 5" /></g></svg>);
const IconBoot = () => (<svg {...mIco}><g {...stroke}><path d="M8 4v9l-3.5 1.5c-.8.3-1.5 1.1-1.5 2v2.5h17.5v-2.7c0-1.4-1-2.5-2.4-2.7l-3.6-.5L13 11V4H8Z" /><path d="M8 9h3.5M5 18h13" /></g></svg>);
const IconMap = () => (<svg {...mIco}><g {...stroke}><path d="m3 6 6-2 6 2 6-2v14l-6 2-6-2-6 2V6Z" /><path d="M9 4v16M15 6v16" /></g></svg>);
const IconPeak = () => (<svg {...mIco}><g {...stroke}><path d="m3 20 7-12 4 6 3-4 4 10H3Z" /><path d="m10 8-1.4 2.4" /></g></svg>);
const bIco = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none" } as const;
const IconBrain = () => (<svg {...bIco}><g {...stroke}><path d="M9 4.5a2.6 2.6 0 0 0-2.6 2.6c-1.4.3-2.4 1.5-2.4 3 0 .9.4 1.7 1 2.2-.6.5-1 1.3-1 2.2 0 1.5 1.2 2.7 2.7 2.7.1 1.4 1.3 2.5 2.7 2.5 1 0 1.8-.5 2.3-1.3" /><path d="M15 4.5a2.6 2.6 0 0 1 2.6 2.6c1.4.3 2.4 1.5 2.4 3 0 .9-.4 1.7-1 2.2.6.5 1 1.3 1 2.2 0 1.5-1.2 2.7-2.7 2.7-.1 1.4-1.3 2.5-2.7 2.5-1 0-1.8-.5-2.3-1.3" /><path d="M12 5v15" /></g></svg>);
const IconBolt = () => (<svg {...bIco}><g {...stroke}><path d="M13 3 5 14h6l-1 7 8-11h-6l1-7Z" /></g></svg>);
const IconTarget = () => (<svg {...bIco}><g {...stroke}><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /></g></svg>);
const IconStar = () => (<svg {...bIco}><g {...stroke}><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17.1l-5.4 2.8 1-6.1L3.2 9.5l6.1-.9L12 3Z" /></g></svg>);
const IconArrowSm = () => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none"><g {...stroke}><path d="M5 12h13M13 6l6 6-6 6" /></g></svg>);

export default function OnboardingFlow({ onDone }: { onDone: () => void }) {
  const { t, tx } = useI18n();
  const [i, setI] = useState(0);
  const [busy, setBusy] = useState(false);
  const [gender, setGender] = useState<string | null>(null);
  const last = i === SLIDES.length - 1;

  const next = async () => {
    if (!last) { setI(i + 1); return; }
    setBusy(true);
    try {
      if (gender) await api.setHeroGender(gender).catch(() => {});
      const batches = await api.listBatches().catch(() => []);
      // Activate a batch the user can actually open: the free showcase batch
      // first, else any unlocked one — and NEVER a locked fallback (the server
      // would 403 it). runBatchAction is the rollback-safe path (AUDIT-2): if
      // the server refuses or the network drops, the local cache is reverted,
      // so onboarding can't leave a ghost "active" batch the deck can't serve.
      const pick = batches.find((b) => b.is_free && !b.locked)
        ?? batches.find((b) => !b.locked);
      if (pick) await runBatchAction(pick.id, "addActive").catch(() => {});
    } catch { /* non-critical */ }
    onDone();
  };

  const s = SLIDES[i];
  return (
    <div className="ob-screen">
      <div className="ob-prog">
        <span className="ob-prog-num">{i + 1} / {SLIDES.length}</span>
        <div className="ob-prog-bars">
          {SLIDES.map((_, k) => <span key={k} className={k <= i ? "on" : ""} />)}
        </div>
        <LangSwitcher variant="ghost" />
      </div>

      {s.kind === "problem" ? (
        <div className="ob-problem">
          <h1 className="ob-pr-head">{t("ob.problem.head")}</h1>
          <p className="ob-pr-sub">{t("ob.problem.sub")}</p>

          <div className="ob-pr-hero">
            <img src={heroProblem} alt="" className="ob-pr-img" />
            <span className="ob-chip ob-chip-1">I would like to discuss…</span>
            <span className="ob-chip ob-chip-2">As far as I'm concerned…</span>
            <span className="ob-chip ob-chip-3">It seems to me…</span>
            <span className="ob-chip ob-chip-4">From my point of view…</span>
            <div className="ob-bubble">{t("ob.problem.bubble")}</div>
          </div>

          <div className="ob-pr-points">
            <div className="ob-pr-point"><IconStack /><span>{t("ob.problem.p1")}</span></div>
            <div className="ob-pr-point"><IconClock /><span>{t("ob.problem.p2")}</span></div>
            <div className="ob-pr-point"><IconArrow /><span>{t("ob.problem.p3")}</span></div>
          </div>

          <div className="ob-insight">
            <span className="ob-insight-label">{t("ob.problem.insightLabel")}</span>
            <p className="ob-insight-text">
              {tx("ob.problem.insight", { b: <b>{t("ob.problem.insightBold")}</b> })}
            </p>
          </div>
        </div>
      ) : s.kind === "why" ? (
        <div className="ob-why">
          <div className="ob-why-hero">
            <img className="ob-why-brain" src={heroBrain} alt="" />
            <h1 className="ob-why-head">{t("ob.why.head")}</h1>
            <p className="ob-why-sub">
              {tx("ob.why.sub", { stories: <b>{t("ob.why.subStories")}</b>, sequences: <b>{t("ob.why.subSequences")}</b> })}
            </p>
          </div>

          <div className="ob-why-rows">
            <div className="ob-why-row">
              <span className="ob-why-ava"><img src={pBartlett} alt="" /></span>
              <div className="ob-why-rtext">
                <b className="ob-why-name">Frederic Bartlett, 1932</b>
                <span className="ob-why-src">Remembering: A Study in Experimental and Social Psychology</span>
                <span className="ob-why-body">{t("ob.why.r1.body")}</span>
              </div>
              <span className="ob-why-chip"><IconBook /></span>
            </div>
            <div className="ob-why-row">
              <span className="ob-why-ava ob-why-ava-glyph"><IconTemple /></span>
              <div className="ob-why-rtext">
                <b className="ob-why-name">{t("ob.why.r2.name")}</b>
                <span className="ob-why-src">{t("ob.why.r2.src")}</span>
                <span className="ob-why-body">{t("ob.why.r2.body")}</span>
              </div>
              <span className="ob-why-chip"><IconPin /></span>
            </div>
            <div className="ob-why-row">
              <span className="ob-why-ava"><img src={pMiller} alt="" /></span>
              <div className="ob-why-rtext">
                <b className="ob-why-name">George A. Miller, 1956</b>
                <span className="ob-why-src">The Magical Number Seven, Plus or Minus Two</span>
                <span className="ob-why-body">{t("ob.why.r3.body")}</span>
              </div>
              <span className="ob-why-chip"><IconChunks /></span>
            </div>
            <div className="ob-why-row">
              <span className="ob-why-ava ob-why-ava-glyph"><IconWings /></span>
              <div className="ob-why-rtext">
                <b className="ob-why-name">{t("ob.why.r4.name")}</b>
                <span className="ob-why-src">{t("ob.why.r4.src")}</span>
                <span className="ob-why-body">{t("ob.why.r4.body")}</span>
              </div>
              <span className="ob-why-chip"><IconChecklist /></span>
            </div>
          </div>

          <div className="ob-why-key">
            <div className="ob-why-key-art"><img src={whyMountain} alt="" /></div>
            <div className="ob-why-key-text">
              <p className="ob-why-key-big">{t("ob.why.keyBig")}</p>
              <span className="ob-why-key-rule" />
              <p className="ob-why-key-sm">
                {tx("ob.why.keySm", { natural: <b>{t("ob.why.keySmNatural")}</b>, long: <b>{t("ob.why.keySmLong")}</b> })}
              </p>
            </div>
          </div>

          <div className="ob-why-foot">
            <span className="ob-why-bulb"><IconBulb /></span>
            <div className="ob-why-foot-text">
              <b>{t("ob.why.footTitle")}</b>
              <span>{t("ob.why.footSub")}</span>
            </div>
          </div>
        </div>
      ) : s.kind === "method" ? (
        <div className="ob-method">
          <h1 className="ob-mt-head">{t("ob.method.head")}</h1>
          <p className="ob-mt-sub">{t("ob.method.sub")}</p>

          <div className="ob-method-hero">
            <img src={heroMethod} alt="" className="ob-method-photo" />

            {/* SVG trail overlay — single continuous glowing route through the 4 nodes */}
            <svg className="ob-mt-trail" viewBox="0 0 100 150" preserveAspectRatio="none" fill="none" aria-hidden xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="obTrailGold" x1="20" y1="140" x2="70" y2="16" gradientUnits="userSpaceOnUse">
                  <stop offset="0" stopColor="#E9C97A" />
                  <stop offset="0.5" stopColor="#D8B25E" />
                  <stop offset="1" stopColor="#F2DFA0" />
                </linearGradient>
                <filter id="obTrailBloom" x="-60%" y="-60%" width="220%" height="220%">
                  <feGaussianBlur stdDeviation="2.6" />
                </filter>
                <filter id="obTrailGlow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="1.1" />
                </filter>
              </defs>
              {/* dark underlay — seats the ribbon on bright rock for contrast */}
              <path className="ob-mt-trail-under" d="M20,141 C26,127 30,114 34,102 C38,90 40,85 44,81 C49,77 50,71 52,60 C54,49 55,45 58,39 C61,33 67,25 70,16.5" stroke="#3A2A12" strokeWidth="4.4" strokeLinecap="round" opacity="0.28" filter="url(#obTrailGlow)" />
              {/* soft outer bloom */}
              <path className="ob-mt-trail-bloom" d="M20,141 C26,127 30,114 34,102 C38,90 40,85 44,81 C49,77 50,71 52,60 C54,49 55,45 58,39 C61,33 67,25 70,16.5" stroke="#F4DE9C" strokeWidth="5.2" strokeLinecap="round" opacity="0.34" filter="url(#obTrailBloom)" />
              {/* mid glow */}
              <path className="ob-mt-trail-glow" d="M20,141 C26,127 30,114 34,102 C38,90 40,85 44,81 C49,77 50,71 52,60 C54,49 55,45 58,39 C61,33 67,25 70,16.5" stroke="#EBCB7E" strokeWidth="3.6" strokeLinecap="round" opacity="0.6" filter="url(#obTrailGlow)" />
              {/* bright confident core */}
              <path className="ob-mt-trail-core" d="M20,141 C26,127 30,114 34,102 C38,90 40,85 44,81 C49,77 50,71 52,60 C54,49 55,45 58,39 C61,33 67,25 70,16.5" stroke="url(#obTrailGold)" strokeWidth="2.1" strokeLinecap="round" />
              {[{ x: 34, y: 102 }, { x: 44, y: 81 }, { x: 52, y: 60 }, { x: 58, y: 39 }].map((n, k) => (
                <g key={k}>
                  <circle cx={n.x} cy={n.y} r="4.2" fill="#EBCB7E" opacity="0.4" filter="url(#obTrailGlow)" />
                  <circle cx={n.x} cy={n.y} r="2.4" fill="url(#obTrailGold)" />
                  <circle cx={n.x} cy={n.y} r="1.5" fill="#FFFDF7" />
                </g>
              ))}
            </svg>

            <span className="ob-method-grad-top" aria-hidden />
            <span className="ob-method-grad-bot" aria-hidden />

            {/* Pins — hero-relative, sit exactly on the SVG nodes (shared coords) */}
            <div className="ob-mt-pins" aria-hidden>
              <span className="ob-mt-pin ob-mt-n1">1</span>
              <span className="ob-mt-pin ob-mt-n2">2</span>
              <span className="ob-mt-pin ob-mt-n3">3</span>
              <span className="ob-mt-pin ob-mt-n4">4</span>
            </div>

            {/* Anchor cards — hero-relative, right-aligned, centered on each node y */}
            <div className="ob-mt-cards">
              <div className="ob-mt-anchor ob-mt-n1">
                <div className="ob-mt-card-head"><span className="ob-mt-icochip"><IconMagnifier /></span><span className="ob-mt-anchor-name">UNDERSTAND</span></div>
                <span className="ob-mt-rule" />
                <p className="ob-mt-ex">Help me <em>understand</em> the thinking there.</p>
              </div>
              <div className="ob-mt-anchor ob-mt-n2">
                <div className="ob-mt-card-head"><span className="ob-mt-icochip"><IconBoot /></span><span className="ob-mt-anchor-name">WALK</span></div>
                <span className="ob-mt-rule" />
                <p className="ob-mt-ex"><em>Walk</em> me through how you got to that number.</p>
              </div>
              <div className="ob-mt-anchor ob-mt-n3">
                <div className="ob-mt-card-head"><span className="ob-mt-icochip"><IconMap /></span><span className="ob-mt-anchor-name">READ</span></div>
                <span className="ob-mt-rule" />
                <p className="ob-mt-ex">Can I offer a different <em>read</em>?</p>
              </div>
              <div className="ob-mt-anchor ob-mt-n4">
                <div className="ob-mt-card-head"><span className="ob-mt-icochip"><IconPeak /></span><span className="ob-mt-anchor-name">FAR</span></div>
                <span className="ob-mt-rule" />
                <p className="ob-mt-ex">I'm not sure I'd go that <em>far</em>.</p>
              </div>
            </div>

            {/* Stage — mnemo (top-left) + bottom bar (don't touch the trail) */}
            <div className="ob-method-stage">
              <div className="ob-mt-mnemo">
                <div className="ob-mt-mnemo-head">
                  <span className="ob-mt-mnemo-chip"><IconPeak /></span>
                  <span className="ob-mt-mnemo-title">{t("ob.method.mnemoTitle")}</span>
                </div>
                <p className="ob-mt-mnemo-body">
                  {tx("ob.method.mnemoBody", { a1: <b>UNDERSTAND</b>, a2: <b>WALK</b>, a3: <b>READ</b>, a4: <b>FAR</b> })}
                </p>
                <div className="ob-mt-mnemo-row">
                  <span className="ob-mt-mnemo-step"><span className="ob-mt-mnemo-ico"><IconMagnifier /></span><span className="ob-mt-mnemo-lbl">UNDERSTAND</span></span>
                  <IconArrowSm />
                  <span className="ob-mt-mnemo-step"><span className="ob-mt-mnemo-ico"><IconBoot /></span><span className="ob-mt-mnemo-lbl">WALK</span></span>
                  <IconArrowSm />
                  <span className="ob-mt-mnemo-step"><span className="ob-mt-mnemo-ico"><IconMap /></span><span className="ob-mt-mnemo-lbl">READ</span></span>
                  <IconArrowSm />
                  <span className="ob-mt-mnemo-step"><span className="ob-mt-mnemo-ico"><IconPeak /></span><span className="ob-mt-mnemo-lbl">FAR</span></span>
                </div>
                <span className="ob-mt-mnemo-foot">{t("ob.method.mnemoFoot")}</span>
              </div>

              <div className="ob-mt-bottom">
                <div className="ob-mt-bottom-l">
                  <span className="ob-mt-brain"><IconBrain /></span>
                  <div className="ob-mt-bottom-text">
                    <b>{t("ob.method.bottomTitle")}</b>
                    <span>{t("ob.method.bottomSub")}</span>
                  </div>
                </div>
                <div className="ob-mt-bottom-r">
                  <div className="ob-mt-benefit"><IconBolt /><span>{t("ob.method.benefit1")}</span></div>
                  <div className="ob-mt-benefit"><IconTarget /><span>{t("ob.method.benefit2")}</span></div>
                  <div className="ob-mt-benefit"><IconStar /><span>{t("ob.method.benefit3")}</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : s.kind === "gender" ? (
        <div className="ob-gender">
          <h1 className="ob-gender-head">{t("ob.gender.head")}</h1>
          <p className="ob-gender-sub">{t("ob.gender.sub")}</p>
          <div className="ob-gender-opts">
            {([
              ["male", "♂", "ob.gender.maleSub"],
              ["female", "♀", "ob.gender.femaleSub"],
              ["mixed", "⚥", "ob.gender.mixedSub"],
            ] as const).map(([code, glyph, sub]) => (
              <button key={code} type="button"
                className={`ob-gender-opt${gender === code ? " sel" : ""}`}
                aria-pressed={gender === code}
                onClick={() => setGender(code)}>
                <span className="ob-gender-glyph" aria-hidden>{glyph}</span>
                <span className="ob-gender-txt">
                  <b>{t(`gender.${code}`)}</b>
                  <span>{t(sub)}</span>
                </span>
                {gender === code && <span className="ob-gender-tick" aria-hidden>✓</span>}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="ob-foot">
        <button className="ob-cta" onClick={next} disabled={busy || (last && !gender)}>
          {busy ? "…" : last ? t("ob.cta.start") : t("ob.cta.next")}
        </button>
        {!last && <button className="ob-skip" type="button" onClick={onDone}>{t("ob.skip")}</button>}
      </div>
    </div>
  );
}
