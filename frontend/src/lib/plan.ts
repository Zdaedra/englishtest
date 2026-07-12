// THE learning-plan order — one source of truth for the map spine, the home
// "Current focus" card, and a batch's "Урок N" position.
//
// Before this, three screens computed the order three different ways: the map
// wove a domain-apportioned trajectory + manual path_rank override; the home
// hero ran buildSprint (which ignored manual mode AND path_rank); BatchHome ran
// a section-priority + created_at flatten. So the home focus, the map's active
// node, and the lesson number could all disagree after a reorder or in manual
// mode. buildPlan() is that ordering, computed once here and consumed by all
// three — change the plan in one place and every surface follows.

import { BatchListItem } from "../api";
import { orderedSections } from "./sections";
import { buildManualTrajectory, buildTrajectory, type Trajectory } from "./strategy";
import { getPlanMode, getProfile, getStrategy, manualIds, prioritySectionSlugs } from "./profile";
import { getProgress } from "./progress";

export type Plan = {
  order: BatchListItem[];          // canonical flat order (map spine == focus source == lesson index)
  domainOf: Map<number, string>;   // batchId → focus-bucket key (per-sprint mix chips)
  activeId: number | null;         // the single active node: first not-yet-closed batch
};

const closed = (id: number) => !!getProgress(id).l3_passed;

/** The canonical plan for this account, right now. Auto mode weaves the
 *  domain-apportioned trajectory; manual mode uses the hand-picked order. Either
 *  way a per-batch path_rank drag is layered on top as a total override (exactly
 *  the map's own logic), so every surface reads the SAME order. */
export function buildPlan(batches: BatchListItem[]): Plan {
  // "Remove from path" (on_path === false) takes a batch OFF the map — and, via
  // this one planner, off the home focus and lesson numbering too. Never-touched
  // (undefined) and added (true) stay, so a fresh learner still sees the whole
  // curriculum woven ahead; the map isn't a subscription list, it's the field.
  const onPlan = batches.filter((b) => getProgress(b.id).on_path !== false);
  const strategy = getStrategy();
  const traj: Trajectory = getPlanMode() === "manual"
    ? buildManualTrajectory(manualIds(), strategy, onPlan)
    : buildTrajectory(
        strategy, onPlan,
        prioritySectionSlugs(getProfile(), orderedSections().map((x) => x.slug)));

  const baseIndex = new Map(traj.order.map((b, i) => [b.id, i] as const));
  const order = traj.order.slice().sort((a, b) => {
    const ra = getProgress(a.id).path_rank;
    const rb = getProgress(b.id).path_rank;
    const ka = ra == null ? baseIndex.get(a.id)! : ra;
    const kb = rb == null ? baseIndex.get(b.id)! : rb;
    if (ka !== kb) return ka - kb;
    return baseIndex.get(a.id)! - baseIndex.get(b.id)!;
  });

  let activeId: number | null = null;
  for (const b of order) if (!closed(b.id)) { activeId = b.id; break; }
  return { order, domainOf: traj.domainOf, activeId };
}

/** The home "Current focus" batch: the plan's active node, but skipping locked
 *  (freemium) content so the hero never lands on a paywalled batch that would
 *  play an empty session. On paid plans nothing is locked, so this is exactly
 *  the map's active node — home and map always agree. */
export function planFocus(batches: BatchListItem[]): BatchListItem | undefined {
  if (!batches.length) return undefined;
  const { order } = buildPlan(batches);
  const openIncomplete = order.find((b) => !b.locked && !closed(b.id));
  return openIncomplete ?? order.find((b) => !b.locked) ?? order[0];
}

/** A batch's 1-based position in the canonical plan (BatchHome "Урок N").
 *  0 when the batch isn't placed (shouldn't happen for a visible batch). */
export function planPosition(batches: BatchListItem[], batchId: number): number {
  const i = buildPlan(batches).order.findIndex((b) => b.id === batchId);
  return i < 0 ? 0 : i + 1;
}
