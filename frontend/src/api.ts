import { isNative, authHeaders } from "./lib/session";
import { getLang } from "./i18n";

// Active content language for catalog GETs. The backend resolves ?lang= →
// localized title/gloss/story (falling back to ru). English-being-learned (anchors,
// phrase_en) always stays English regardless of this.
const clang = () => getLang();

export type Phrase = {
  id: number; order_index: number; anchor: string; phrase_en: string;
  gloss_ru: string; intensity_score: number; zone_id: number | null; srs_status: string;
};
export type Zone = { id: number; title: string; order_index: number; intensity_label: string };
export type Span = { anchor_id: string; phrase_id: number; start: number; end: number };
export type Mnemo = { story_ru: string; spans: Span[] };
export type BatchDetail = {
  id: number; title: string; slug: string; theme: string; subtitle: string; status: string;
  cover_url: string | null; is_free?: boolean; locked?: boolean;
  zones: Zone[]; phrases: Phrase[]; mnemo: Mnemo;
};
export type BatchListItem = {
  id: number; title: string; slug: string; theme: string; subtitle: string;
  section: string; preview: string; status: string;
  phrase_count: number; anchors: string[]; cover_url: string | null;
  is_free?: boolean; locked?: boolean;
  created_at: string;
};
export type PlanSeg = {
  kind: "audio" | "silence"; role: string; phrase_order: number | null;
  text?: string; lang?: string; anchor_id?: string; start: number; end: number;
};
export type SessionResp = {
  id: number; batch_id: number; mode: string; order_mode: string;
  audio_url: string; duration: number; plan: PlanSeg[];
};
export type PhraseScore = {
  phrase_id: number; anchor: string; transcript: string; score: number;
  correct_phrase: string; via: string; avg_score: number | null; attempts: number;
};
export type SequenceScore = {
  batch_id: number; transcript: string; score: number;
  missed_anchors: string[]; order_ok: boolean; passed: boolean; via: string;
};
export type AnchorScore = {
  phrase_id: number; anchor: string; transcript: string; score: number;
  correct_anchor: string; via: string;
};
export type RotationItem = {
  phrase_id: number; anchor: string; order_index: number;
  avg_score: number | null; attempts: number; last_score: number | null;
};
export type BatchMastery = {
  batch_id: number; avg_score: number | null; attempts: number;
  last_seen_at: string | null;
  // SM-2-lite schedule rollup: phrases due now, when the next is due, and the
  // qualitative state breakdown (new/shaky/familiar/automatic).
  due?: number; next_review_at?: string | null; srs?: Record<string, number>;
  // Confidence-calibration gap: swiped "known" but never produced aloud (or weakly).
  gap?: number;
};
export type PhraseSearchItem = {
  phrase_id: number; batch_id: number; batch_title: string;
  anchor: string; phrase_en: string; gloss_ru: string; order_index: number;
};
export type PracticeQuestion = {
  id: string; batch_id: number; batch_title: string; prompt_ru: string;
  zone: string; accept_phrase_ids: number[]; hint_anchor: string;
};
export type PracticeScore = {
  score: number; phrase_id: number; anchor: string; phrase_en: string;
  transcript: string; is_repeat: boolean;
};
// --- Swipe-deck Training -----------------------------------------------------
export type DeckCard = {
  phrase_id: number; batch_id: number; batch_title: string; section: string;
  slug: string; cover_url: string | null;
  anchor: string; phrase_en: string;
  stimulus: string; stimulus_id: number | null; stimulus_lang: string;
  gloss_ru: string; conf: number; priority: number;
  attempts: number; avg_score: number | null;
  ai_allowed?: boolean; // mic/AI usable on this card's batch (free showcase batch or ai plan)
};
export type AnswerResult = {
  event_id: number; phrase_id: number; anchor: string; transcript: string;
  score: number; correct_phrase: string; feedback: string; via: string;
  avg_score: number | null; attempts: number; auto_success: boolean;
};
export type SessionSummary = {
  session_id: string; cards_total: number; cards_known: number; cards_unknown: number;
  avg_score: number | null;
  weakest: { batch_id: number; batch_title: string; success_rate: number } | null;
  strongest: { batch_id: number; batch_title: string; success_rate: number } | null;
  by_batch: { batch_id: number; batch_title: string; total: number; known: number; success_rate: number }[];
};
export type Coach = {
  feedback: string; better: string; tone: string; correct_phrase: string; via: string;
};
export type ProgressRow = {
  batch_id: number; activated: boolean; activated_at: string | null;
  l1_listened: boolean; l1_retold: boolean; l1_best_seq: number | null;
  l3_s1: boolean; l3_s2: boolean; l3_passed: boolean; completed_at: string | null;
};

export type Entitlements = {
  voice_answer: boolean; server_stt: boolean; ai_coach: boolean; import: boolean;
  max_active_batches: number | null; scored_per_day: number;
};
export type Me = { id: number; email: string; name: string; plan: string; is_admin?: boolean; ui_lang?: string | null; entitlements?: Entitlements; token?: string };

// Web: same-origin, "" → relative paths, cookie auth. Native (Capacitor): the
// webview origin is capacitor://localhost, so the API needs an absolute base and
// a Bearer token (no cross-origin cookie). VITE_API_BASE overrides the default.
export const API_BASE = isNative()
  ? (((import.meta as any).env?.VITE_API_BASE as string) || "https://executive-english.net")
  : "";

/** Prefix backend-relative media paths (cover/audio URLs) with the API base so
 *  they resolve on native. No-op on web (API_BASE === ""). */
export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return path ?? null;
  return path.startsWith("http") ? path : API_BASE + path;
}

/** fetch wrapper: applies the API base + the native Bearer header. */
function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(API_BASE + path, {
    ...init,
    headers: { ...authHeaders(), ...((init?.headers as Record<string, string>) || {}) },
  });
}

// Global 401 handler — when a session expires mid-use, the AuthProvider hooks
// this to drop back to the login screen.
let _onUnauthorized: (() => void) | null = null;
export function setOnUnauthorized(cb: () => void) { _onUnauthorized = cb; }

async function j<T>(r: Response): Promise<T> {
  if (r.status === 401) _onUnauthorized?.();
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

export const api = {
  listBatches: () => apiFetch(`/api/batches?lang=${clang()}`).then(j<BatchListItem[]>),
  getBatch: (id: number) => apiFetch(`/api/batches/${id}?lang=${clang()}`).then(j<BatchDetail>),
  phraseAudio: (phraseId: number) =>
    apiFetch(`/api/batches/phrase/${phraseId}/audio`).then(
      j<{ audio_url: string; duration: number }>
    ).then((r) => ({ ...r, audio_url: mediaUrl(r.audio_url)! })),
  mnemoAudio: (batchId: number, layout: "full" | "anchors" | "shuffle") =>
    apiFetch(`/api/batches/${batchId}/mnemo/audio?layout=${layout}&lang=${clang()}`).then(
      j<{ audio_url: string; duration: number; plan: PlanSeg[]; layout: string }>
    ).then((r) => ({ ...r, audio_url: mediaUrl(r.audio_url)! })),
  deleteBatch: (id: number) =>
    apiFetch(`/api/batches/${id}`, { method: "DELETE" }).then(j<{ ok: boolean }>),
  parse: (raw_text: string, use_llm = false) =>
    apiFetch("/api/imports/parse", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ raw_text, use_llm }),
    }).then(j<{ batch: any; warnings: string[]; parser: string }>),
  commit: (batch: any) =>
    apiFetch("/api/imports/commit", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(batch),
    }).then(j<{ id: number; slug: string; status: string }>),
  createSession: (req: {
    batch_id: number; mode: string; order_mode: string;
    voice?: string; repeats?: number;
  }) =>
    apiFetch("/api/sessions", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(req),
    }).then(j<SessionResp>).then((r) => ({ ...r, audio_url: mediaUrl(r.audio_url)! })),
  review: (phrase_id: number, score: string) =>
    apiFetch("/api/batches/reviews", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ phrase_id, score }),
    }).then(j<{ phrase_id: number; srs_status: string }>),
  scorePhrase: (phraseId: number, audio: Blob, filename: string, latencyMs?: number) => {
    const fd = new FormData();
    fd.append("audio", audio, filename);
    fd.append("phrase_id", String(phraseId));
    if (latencyMs != null) fd.append("latency_ms", String(latencyMs));
    return apiFetch("/api/training/score-phrase", { method: "POST", body: fd }).then(j<PhraseScore>);
  },
  scoreSequence: (batchId: number, audio: Blob, filename: string, latencyMs?: number) => {
    const fd = new FormData();
    fd.append("audio", audio, filename);
    fd.append("batch_id", String(batchId));
    if (latencyMs != null) fd.append("latency_ms", String(latencyMs));
    return apiFetch("/api/training/score-sequence", { method: "POST", body: fd }).then(j<SequenceScore>);
  },
  scoreAnchor: (phraseId: number, audio: Blob, filename: string, latencyMs?: number) => {
    const fd = new FormData();
    fd.append("audio", audio, filename);
    fd.append("phrase_id", String(phraseId));
    if (latencyMs != null) fd.append("latency_ms", String(latencyMs));
    return apiFetch("/api/training/score-anchor", { method: "POST", body: fd }).then(j<AnchorScore>);
  },
  listPhrases: () => apiFetch(`/api/batches/phrases?lang=${clang()}`).then(j<PhraseSearchItem[]>),
  getPracticeQuestions: (batchIds: number[]) =>
    apiFetch(`/api/practice/questions?batch_ids=${batchIds.join(",")}`).then(
      j<{ questions: PracticeQuestion[] }>
    ),
  practicePromptAudio: (text: string) => {
    const fd = new FormData();
    fd.append("text", text);
    return apiFetch("/api/practice/prompt-audio", { method: "POST", body: fd }).then(
      j<{ audio_url: string; duration: number }>
    ).then((r) => ({ ...r, audio_url: mediaUrl(r.audio_url)! }));
  },
  practiceScore: (
    phraseIds: number[], usedPhraseIds: number[], audio: Blob, filename: string, latencyMs?: number
  ) => {
    const fd = new FormData();
    fd.append("audio", audio, filename);
    fd.append("phrase_ids", phraseIds.join(","));
    fd.append("used_phrase_ids", usedPhraseIds.join(","));
    if (latencyMs != null) fd.append("latency_ms", String(latencyMs));
    return apiFetch("/api/practice/score", { method: "POST", body: fd }).then(j<PracticeScore>);
  },
  getRotation: (batchId: number) =>
    apiFetch(`/api/training/rotation/${batchId}`).then(j<RotationItem[]>),
  getMastery: () => apiFetch("/api/training/mastery").then(j<BatchMastery[]>),
  // --- Swipe-deck Training ---
  getDeck: (batchIds: number[], opts?: { maintenanceIds?: number[]; limit?: number; exclude?: number[]; dueOnly?: boolean; gapOnly?: boolean }) => {
    const q = new URLSearchParams({ batch_ids: batchIds.join(",") });
    if (opts?.maintenanceIds?.length) q.set("maintenance_ids", opts.maintenanceIds.join(","));
    if (opts?.limit) q.set("limit", String(opts.limit));
    if (opts?.exclude?.length) q.set("exclude", opts.exclude.join(","));
    if (opts?.dueOnly) q.set("due_only", "1");
    if (opts?.gapOnly) q.set("gap_only", "1");
    q.set("lang", clang());
    return apiFetch(`/api/training/deck?${q}`).then(j<DeckCard[]>);
  },
  trainSwipe: (sessionId: string, phraseId: number, dir: "left" | "right", ms?: number) =>
    apiFetch("/api/training/swipe", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, phrase_id: phraseId, swipe_direction: dir, response_time_ms: ms ?? null }),
    }).then(j<{ ok: boolean; self_ewma: number }>),
  trainAnswer: (sessionId: string, phraseId: number, audio: Blob, filename: string, latencyMs?: number) => {
    const fd = new FormData();
    fd.append("audio", audio, filename);
    fd.append("phrase_id", String(phraseId));
    fd.append("session_id", sessionId);
    if (latencyMs != null) fd.append("latency_ms", String(latencyMs));
    return apiFetch("/api/training/answer", { method: "POST", body: fd }).then(j<AnswerResult>);
  },
  trainAnswerText: (sessionId: string, phraseId: number, transcript: string, ms?: number) =>
    apiFetch("/api/training/answer-text", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, phrase_id: phraseId, transcript, response_time_ms: ms ?? null }),
    }).then(j<AnswerResult>),
  trainAnswerConfirm: (eventId: number, manualSuccess: boolean) =>
    apiFetch("/api/training/answer/confirm", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ event_id: eventId, manual_success: manualSuccess }),
    }).then(j<{ ok: boolean }>),
  trainSummary: (sessionId: string) =>
    apiFetch(`/api/training/session/${sessionId}/summary?lang=${clang()}`).then(j<SessionSummary>),
  coach: (phraseId: number, transcript: string, score: number): Promise<Coach | { locked: true }> =>
    apiFetch("/api/training/coach", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ phrase_id: phraseId, transcript, score }),
    }).then((r) => (r.status === 403 ? { locked: true as const }
      : r.ok ? (r.json() as Promise<Coach>)
        : r.text().then((t) => Promise.reject(new Error(t || r.statusText))))),
  listProgress: () => apiFetch("/api/progress").then(j<ProgressRow[]>),
  putProgress: (batchId: number, patch: Partial<Omit<ProgressRow, "batch_id" | "activated_at" | "completed_at">>) =>
    apiFetch(`/api/progress/${batchId}`, {
      method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify(patch),
    }).then(j<ProgressRow>),
  getSettings: () => apiFetch("/api/settings").then(j<any>),
  putSettings: (patch: any) =>
    apiFetch("/api/settings", {
      method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify(patch),
    }).then(j<any>),
  // --- Auth (commercial multi-user) ---
  me: () => apiFetch("/api/auth/me").then((r) => (r.ok ? (r.json() as Promise<Me>) : null)),
  login: (email: string, password: string) =>
    apiFetch("/api/auth/login", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    }).then(j<Me>),
  register: (email: string, password: string, name?: string) =>
    apiFetch("/api/auth/register", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    }).then(j<Me>),
  logout: () => apiFetch("/api/auth/logout", { method: "POST" }).then((r) => r.ok),
  deleteAccount: () => apiFetch("/api/auth/me", { method: "DELETE" }).then((r) => r.ok),
  // Best-effort UI-language sync (fire-and-forget; ignored when logged out).
  setUiLang: (lang: string) =>
    apiFetch("/api/auth/ui-lang", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ lang }),
    }).then((r) => r.ok).catch(() => false),
};
