// Per-batch lesson progress. Single user, so localStorage is the source of truth
// for the soft milestones the backend doesn't already track (listened to the
// story, did ≥1 retell, passed the final exam). Phrase-level progress for Lesson 2
// is derived live from the rotation endpoint (avg_score / attempts), not stored here.

export type BatchProgress = {
  activated?: boolean; // user tapped "Активировать бетч" — it's now an active batch
  activatedAt?: string; // ISO timestamp of activation (for recency ordering)
  l1_listened?: boolean; // played the full story at least once
  l1_retold?: boolean; // did at least one sequence retell
  l1_best_seq?: number; // best sequence score so far (informational)
  l3_s1?: boolean; // exam stage 1 passed (full retell, avg ≥ 8)
  l3_s2?: boolean; // exam stage 2 passed (story-stop phrase, avg ≥ 8)
  l3_passed?: boolean; // passed the whole 3-stage final exam (all stages ≥ 80%)
};

// A batch is "engaged" (appears in the In Progress count + the Library's active
// row) once the learner has activated it or made any progress.
export function isEngaged(p: BatchProgress): boolean {
  return !!(p.activated || p.l1_listened || p.l1_retold || p.l3_s1 || p.l3_s2 || p.l3_passed);
}

const key = (batchId: number) => `ee-progress-${batchId}`;

export function getProgress(batchId: number): BatchProgress {
  try {
    return JSON.parse(localStorage.getItem(key(batchId)) || "{}");
  } catch {
    return {};
  }
}

export function setProgress(batchId: number, patch: Partial<BatchProgress>): BatchProgress {
  const next = { ...getProgress(batchId), ...patch };
  try {
    localStorage.setItem(key(batchId), JSON.stringify(next));
  } catch {
    /* storage full / disabled — progress is non-critical */
  }
  // Mirror to the server (per-user source of truth). Fire-and-forget; the local
  // cache keeps the UI synchronous. activatedAt/completed_at are server-set.
  const srv: Record<string, unknown> = {};
  for (const k of ["activated", "l1_listened", "l1_retold", "l1_best_seq", "l3_s1", "l3_s2", "l3_passed"] as const) {
    if (k in patch && patch[k] !== undefined) srv[k] = patch[k];
  }
  if (Object.keys(srv).length) {
    import("../api").then(({ api }) => api.putProgress(batchId, srv as any).catch(() => {}));
  }
  return next;
}

// Drop all local progress (on login/logout) so a shared browser never leaks one
// account's progress to another before server hydration.
export function clearLocalProgress(): void {
  try {
    const ks: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith("ee-progress-")) ks.push(k);
    }
    ks.forEach((k) => localStorage.removeItem(k));
  } catch { /* ignore */ }
}

// Pull this user's progress from the server into the local cache (on login).
export async function hydrateProgress(): Promise<void> {
  try {
    const { api } = await import("../api");
    const rows = await api.listProgress();
    rows.forEach((r) => {
      const bp: BatchProgress = {
        activated: r.activated,
        activatedAt: r.activated_at || undefined,
        l1_listened: r.l1_listened,
        l1_retold: r.l1_retold,
        l1_best_seq: r.l1_best_seq ?? undefined,
        l3_s1: r.l3_s1,
        l3_s2: r.l3_s2,
        l3_passed: r.l3_passed,
      };
      try { localStorage.setItem(key(r.batch_id), JSON.stringify(bp)); } catch { /* ignore */ }
    });
  } catch { /* offline / not critical */ }
}

export type LessonState = "locked" | "open" | "done";

// Soft-lock: a lesson is "open" once the previous one is done, "locked" (visually
// dimmed but still tappable) otherwise. Lesson 1 is always open.
export function lessonStates(p: BatchProgress, l2done: boolean): [LessonState, LessonState, LessonState] {
  const l1done = !!(p.l1_listened && p.l1_retold);
  const l3done = !!p.l3_passed;
  return [
    l1done ? "done" : "open",
    l2done ? "done" : l1done ? "open" : "locked",
    l3done ? "done" : l2done ? "open" : "locked",
  ];
}
