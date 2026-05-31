// Zone label shared by the Mnemonic sequence and the Patterns list. The pips show
// where this zone sits on the batch's intensity ladder (e.g. Curious → Direct).
export function ZoneHead({
  title,
  level,
  total,
  count,
}: {
  title: string;
  level: number;
  total: number;
  count?: number;
}) {
  if (!title) return null;
  return (
    <div className="zone-head">
      <span className="zone-name">{title}</span>
      {total > 1 && (
        <span className="zone-pips" aria-hidden>
          {Array.from({ length: total }).map((_, i) => (
            <span key={i} className={`zone-pip${i < level ? " on" : ""}`} />
          ))}
        </span>
      )}
      {count != null && <span className="zone-count">{count}</span>}
    </div>
  );
}
