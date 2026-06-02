export type Phrase = {
  id: number; order_index: number; anchor: string; phrase_en: string;
  gloss_ru: string; intensity_score: number; zone_id: number | null; srs_status: string;
};
export type Zone = { id: number; title: string; order_index: number; intensity_label: string };
export type Span = { anchor_id: string; phrase_id: number; start: number; end: number };
export type Mnemo = { story_ru: string; spans: Span[] };
export type BatchDetail = {
  id: number; title: string; slug: string; theme: string; subtitle: string; status: string;
  cover_url: string | null;
  zones: Zone[]; phrases: Phrase[]; mnemo: Mnemo;
};
export type BatchListItem = {
  id: number; title: string; slug: string; theme: string; subtitle: string;
  section: string; preview: string; status: string;
  phrase_count: number; anchors: string[]; cover_url: string | null;
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
};
export type PhraseSearchItem = {
  phrase_id: number; batch_id: number; batch_title: string;
  anchor: string; phrase_en: string; gloss_ru: string; order_index: number;
};

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

export const api = {
  listBatches: () => fetch("/api/batches").then(j<BatchListItem[]>),
  getBatch: (id: number) => fetch(`/api/batches/${id}`).then(j<BatchDetail>),
  phraseAudio: (phraseId: number) =>
    fetch(`/api/batches/phrase/${phraseId}/audio`).then(
      j<{ audio_url: string; duration: number }>
    ),
  mnemoAudio: (batchId: number, layout: "full" | "anchors" | "shuffle") =>
    fetch(`/api/batches/${batchId}/mnemo/audio?layout=${layout}`).then(
      j<{ audio_url: string; duration: number; plan: PlanSeg[]; layout: string }>
    ),
  deleteBatch: (id: number) =>
    fetch(`/api/batches/${id}`, { method: "DELETE" }).then(j<{ ok: boolean }>),
  parse: (raw_text: string, use_llm = false) =>
    fetch("/api/imports/parse", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ raw_text, use_llm }),
    }).then(j<{ batch: any; warnings: string[]; parser: string }>),
  commit: (batch: any) =>
    fetch("/api/imports/commit", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(batch),
    }).then(j<{ id: number; slug: string; status: string }>),
  createSession: (req: {
    batch_id: number; mode: string; order_mode: string;
    voice?: string; repeats?: number;
  }) =>
    fetch("/api/sessions", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(req),
    }).then(j<SessionResp>),
  review: (phrase_id: number, score: string) =>
    fetch("/api/batches/reviews", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ phrase_id, score }),
    }).then(j<{ phrase_id: number; srs_status: string }>),
  scorePhrase: (phraseId: number, audio: Blob, filename: string, latencyMs?: number) => {
    const fd = new FormData();
    fd.append("audio", audio, filename);
    fd.append("phrase_id", String(phraseId));
    if (latencyMs != null) fd.append("latency_ms", String(latencyMs));
    return fetch("/api/training/score-phrase", { method: "POST", body: fd }).then(j<PhraseScore>);
  },
  scoreSequence: (batchId: number, audio: Blob, filename: string, latencyMs?: number) => {
    const fd = new FormData();
    fd.append("audio", audio, filename);
    fd.append("batch_id", String(batchId));
    if (latencyMs != null) fd.append("latency_ms", String(latencyMs));
    return fetch("/api/training/score-sequence", { method: "POST", body: fd }).then(j<SequenceScore>);
  },
  scoreAnchor: (phraseId: number, audio: Blob, filename: string, latencyMs?: number) => {
    const fd = new FormData();
    fd.append("audio", audio, filename);
    fd.append("phrase_id", String(phraseId));
    if (latencyMs != null) fd.append("latency_ms", String(latencyMs));
    return fetch("/api/training/score-anchor", { method: "POST", body: fd }).then(j<AnchorScore>);
  },
  listPhrases: () => fetch("/api/batches/phrases").then(j<PhraseSearchItem[]>),
  getRotation: (batchId: number) =>
    fetch(`/api/training/rotation/${batchId}`).then(j<RotationItem[]>),
  getMastery: () => fetch("/api/training/mastery").then(j<BatchMastery[]>),
  getSettings: () => fetch("/api/settings").then(j<any>),
  putSettings: (patch: any) =>
    fetch("/api/settings", {
      method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify(patch),
    }).then(j<any>),
};
