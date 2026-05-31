// One unified, restrained accent across the whole app — a premium "knowledge
// library" feel rather than a rainbow of per-batch colours. Visual variety now
// comes from each batch's generative art (ui/Art.tsx), not from chrome colour.
// Warm graphite ink for solid affordances; no blue anywhere.
export type Accent = { name: string; color: string; tint: string; grad: string };

const INK: Accent = {
  name: "Ink",
  color: "#26211B",
  tint: "#EFEAE1",
  grad: "linear-gradient(150deg,#3C342B,#211C16)",
};

// Signature kept (id arg) so call-sites are untouched; the accent is unified.
export function accentFor(_id: number): Accent {
  return INK;
}

// Inline CSS custom-property vars to scope an accent to a subtree.
export function accentVars(a: Accent): React.CSSProperties {
  return {
    ["--accent" as any]: a.color,
    ["--accent-tint" as any]: a.tint,
    ["--accent-grad" as any]: a.grad,
  };
}

export function fmtTime(s: number): string {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}
