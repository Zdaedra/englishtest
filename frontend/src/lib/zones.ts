import { BatchDetail, Phrase } from "../api";

export type ZoneGroup = {
  key: string;
  title: string;
  level: number; // 1-based position of this zone in the ladder
  total: number; // total number of zones (for the intensity pips)
  items: { p: Phrase; n: number }[]; // n = global 1-based order across the batch
};

// Group phrases into their zones, preserving the batch order. Phrases already sit
// contiguously by zone (the authoring order is the ladder), so consecutive runs of
// the same zone_id become one group. `n` keeps the global anchor number so the
// Mnemonic sequence still reads 1..N across the zone breaks.
export function groupByZone(batch: BatchDetail): ZoneGroup[] {
  const ordered = [...batch.phrases].sort((a, b) => a.order_index - b.order_index);
  const zonesSorted = [...batch.zones].sort((a, b) => a.order_index - b.order_index);
  const total = zonesSorted.length;
  const zoneById = new Map(zonesSorted.map((z) => [z.id, z]));
  const levelById = new Map(zonesSorted.map((z, i) => [z.id, i + 1]));

  const groups: ZoneGroup[] = [];
  ordered.forEach((p, i) => {
    const key = p.zone_id == null ? "none" : String(p.zone_id);
    const last = groups[groups.length - 1];
    if (!last || last.key !== key) {
      const z = p.zone_id == null ? undefined : zoneById.get(p.zone_id);
      groups.push({
        key,
        title: z?.title ?? "",
        level: p.zone_id == null ? 0 : levelById.get(p.zone_id) ?? 0,
        total,
        items: [],
      });
    }
    groups[groups.length - 1].items.push({ p, n: i + 1 });
  });
  return groups;
}
