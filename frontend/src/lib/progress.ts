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
  return next;
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
