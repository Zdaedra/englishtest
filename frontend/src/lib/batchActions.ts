// Single source of truth for the long-press batch menu: which items to show for a
// batch's current state, and how to execute each action. State model (two axes):
//   on_path = curated learning trajectory (Learning map) · activated = practice deck
//   invariant: activated ⊆ on_path. See TZ-batch-management.md §12.
import { api } from "../api";
import { getProgress, setProgress, writeLocalProgress, BatchProgress } from "./progress";

export type BatchAction =
  | "addPath" | "removePath" | "addActive" | "removeActive" | "reactivate"
  | "moveUp" | "moveDown" | "moveStart" | "moveEnd" | "open";

export type MenuItem = { action: BatchAction; labelKey: string; destructive?: boolean };

const OPEN: MenuItem = { action: "open", labelKey: "batch.menu.open" };
const REMOVE_PATH: MenuItem = { action: "removePath", labelKey: "batch.menu.removePath", destructive: true };

// Reorder context — the surface that draws the queue (Learning) registers, per
// batch, the ordered id list of its section siblings. Lets the generic menu offer
// "move up/down in queue" only where reordering is meaningful (and not in Library).
let queueSiblings: Record<number, number[]> = {};
export function setQueueSiblings(map: Record<number, number[]>): void { queueSiblings = map; }
export function clearQueueSiblings(): void { queueSiblings = {}; }

// Always offer BOTH axes: each shows "add" if the batch isn't in that set, or
// "remove" if it is. (active ⊆ on_path, so an active batch is on-path too.)
export function batchMenuItems(batchId: number): MenuItem[] {
  const p = getProgress(batchId);
  const active = !!p.activated;
  const onPath = !!p.on_path || active;   // invariant: active ⟹ on_path
  const completed = !!p.l3_passed;
  const items: MenuItem[] = [];
  // Queue reorder (only where a sibling order is registered, i.e. the Learning map).
  // The sibling list is the whole plan, so these move across sprint boundaries.
  const sibs = queueSiblings[batchId];
  if (sibs && sibs.length > 1) {
    const i = sibs.indexOf(batchId);
    if (i > 0) {
      items.push({ action: "moveStart", labelKey: "batch.menu.moveStart" });
      items.push({ action: "moveUp", labelKey: "batch.menu.moveUp" });
    }
    if (i >= 0 && i < sibs.length - 1) {
      items.push({ action: "moveDown", labelKey: "batch.menu.moveDown" });
      items.push({ action: "moveEnd", labelKey: "batch.menu.moveEnd" });
    }
  }
  // Active axis (practice-deck rotation)
  if (active) items.push({ action: "removeActive", labelKey: "batch.menu.removeActive" });
  else if (completed) items.push({ action: "reactivate", labelKey: "batch.menu.reactivate" });
  else items.push({ action: "addActive", labelKey: "batch.menu.addActive" });
  // Trajectory axis (learning path)
  items.push(onPath
    ? REMOVE_PATH
    : { action: "addPath", labelKey: "batch.menu.addPath" });
  items.push(OPEN);
  return items;
}

type PatchAction = "addPath" | "removePath" | "addActive" | "removeActive" | "reactivate";
const PATCHES: Record<PatchAction, Partial<BatchProgress>> = {
  addPath: { on_path: true },
  removePath: { on_path: false, activated: false },  // leaving the path drops the deck too
  addActive: { on_path: true, activated: true },
  reactivate: { on_path: true, activated: true },
  removeActive: { activated: false },
};

// Queue reorder. up/down swap with a neighbour; start/end lift the batch to the
// very front / back of the plan. Either way we re-index the whole sibling
// group's path_rank (0…n) so the new order is total and stable. setProgress
// mirrors each rank to the server, so the manual order survives devices.
type ReorderDir = -1 | 1 | "start" | "end";
function reorder(batchId: number, dir: ReorderDir): void {
  const sibs = queueSiblings[batchId];
  if (!sibs) return;
  const i = sibs.indexOf(batchId);
  if (i < 0) return;
  const next = sibs.slice();
  if (dir === "start") {
    if (i === 0) return;
    next.splice(i, 1);
    next.unshift(batchId);
  } else if (dir === "end") {
    if (i === next.length - 1) return;
    next.splice(i, 1);
    next.push(batchId);
  } else {
    const j = i + dir;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
  }
  next.forEach((id, idx) => setProgress(id, { path_rank: idx }));
}

export type ActionResult = { ok: boolean; locked?: boolean };

// Optimistic local write, then drive the server PUT. On ANY failure (cap/lock 403,
// network, 5xx) roll the local cache back to avoid silent divergence, and signal
// `locked` so the caller can upsell. Notifies surfaces via an "ee-progress-changed"
// event so lists re-render. (A retry-queue + LWW reconcile is a documented follow-up.)
export async function runBatchAction(batchId: number, action: BatchAction): Promise<ActionResult> {
  if (action === "open") return { ok: true };
  if (action === "moveUp" || action === "moveDown" || action === "moveStart" || action === "moveEnd") {
    const dir: ReorderDir =
      action === "moveUp" ? -1 : action === "moveDown" ? 1 : action === "moveStart" ? "start" : "end";
    reorder(batchId, dir);
    notifyProgressChanged();
    return { ok: true };
  }
  const patch = PATCHES[action];
  const before = getProgress(batchId);
  writeLocalProgress(batchId, patch);
  notifyProgressChanged();
  try {
    await api.putProgress(batchId, patch as Record<string, unknown>);
    return { ok: true };
  } catch (e) {
    writeLocalProgress(batchId, { on_path: before.on_path, activated: before.activated });
    notifyProgressChanged();
    const msg = String(e);
    const locked = msg.includes("limit_active") || msg.includes("locked") || msg.includes("403");
    return { ok: false, locked };
  }
}

export function notifyProgressChanged(): void {
  try { window.dispatchEvent(new Event("ee-progress-changed")); } catch { /* noop */ }
}
