// Word-level hit map of the model phrase against what the learner actually said —
// the Speak-style visual: hits stay solid, misses light up as the thing to notice.
// Crude inflection tolerance (shared 4-char stem) so "understands"≈"understand".
// Shared by the swipe-trainer result and the Arena beats.
export function diffWords(model: string, said: string): { w: string; hit: boolean }[] {
  const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9']/g, "");
  const heard = said.split(/\s+/).map(norm).filter(Boolean);
  return (model || "").split(/\s+/).map((w) => {
    const n = norm(w);
    const hit = !!n && heard.some((h) =>
      h === n || (h.length >= 4 && n.length >= 4 && h.slice(0, 4) === n.slice(0, 4)));
    return { w, hit };
  });
}

// The model phrase rendered as the word-hit map (falls back to plain text when
// there's no transcript to compare against, e.g. a swipe self-grade).
export function ModelPhrase({ label, model, said }: { label: string; model: string; said?: string }) {
  return (
    <p className="tr-model">
      <span className="tr-result-lbl">{label}</span>
      {said?.trim()
        ? diffWords(model, said).map((x, i) => (
            <span key={i} className={x.hit ? "w-hit" : "w-miss"}>{x.w}{" "}</span>
          ))
        : model}
    </p>
  );
}
