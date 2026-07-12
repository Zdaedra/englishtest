---
description: Author a new learning batch (phrases + mnemonic) from screenshots/a topic via an Opus phrase-consilium, and create it on prod the project's way.
argument-hint: <topic or theme> (and/or attach screenshots of example phrases)
---

You are creating a new **Executive English** learning batch from: $ARGUMENTS

Follow this pipeline exactly (it is the established project skill). Work autonomously; only stop to confirm the curated phrase list + section before writing to prod.

## 1. Gather the seed
- If screenshots are attached, Read each and transcribe every example phrase verbatim. Note any structure the source implies (e.g. moves: transition → recap → dismissal).
- Combine with the topic in $ARGUMENTS into a one-line goal (what real situation this batch trains).

## 2. Phrase consilium (real models, reliable path)
Spawn **2 parallel `Agent` calls, model: opus** (browser GPT/Claude is flaky — use subagents):
- **Expert A — coach lens:** a native NA business-English coach. Produce ~22-28 candidates grouped by the closing/opening/etc. MOVES of this situation, each with: phrase, move, register/intensity 1-5 (warm→decisive), 3-6 word RU function gloss. Include the hard cases execs struggle with.
- **Expert B — authenticity lens:** a skeptical linguist. ~15-20 phrases people ACTUALLY say (vs textbook), grouped by move, intensity, RU gloss + an "AVOID: textbook/cringe" list + the 3-5 highest-value non-obvious ones to drill.
Then YOU curate to **~10 phrases** that form a coherent ARC (one per move + 2-3 hard/high-value), favouring authenticity. For each pick a single distinct English **anchor** word (woven into the mnemo later), the EN phrase, a zone (the move), and a short `gloss_ru`.

## 3. Mnemonic (Opus)
Spawn one `Agent` (model: opus): write a SHORT (4-6 sentences) vivid, deliberately ABSURD Russian мнемо-история that embeds the 10 English anchors **as standalone lowercase Latin words, each exactly once, IN PHRASE ORDER** (spans are auto-computed by case-insensitive substring match advancing a cursor — order + uniqueness + standalone is mandatory). Distinctiveness > realism.

## 4. Decide metadata
- `section`: a slug from `frontend/src/lib/sections.ts`. Business/meetings → `small-talk` ("Small Talk & Meetings"); also pitch / negotiation / leadership / pressure / requests / written.
- Short Russian `title`, a 1-3 word `subtitle` (the mnemo scene), a one-line `theme`.
- **Confirm the curated phrase list + section with the user before writing to prod.**

## 5. Create on prod (server-side, the project's authoring path)
Build a `content.BatchAuthor` and call `content.upsert` inside the container (imports work — the legacy `phrase.srs_status` drift was fixed 2026-06-26; no raw-SQL workaround needed). Pipe a script:
```
ssh -i ~/.ssh/antigravity_key root@89.167.122.76 'docker exec -i -w /srv/backend english_app python -' < /tmp/make_batch.py
```
The script: `from app import content, models`; build `BatchAuthor(slug, title, theme, subtitle, section, zones=[move names], phrases=[PhraseAuthor(anchor, en, zone, gloss_ru)…], mnemo=story)`; `bi,w = content.to_batch_in(author)`; `with Session(engine()) as s: b,created = content.upsert(s, bi, slug=…, auto_title=False, auto_subtitle=False)`. Use a unique kebab `slug`. owner_id stays NULL (shared catalog), is_free False (paid).

## 6. Fill card front + cover
- `docker exec -w /srv/backend english_app python -m app.gen_context --batch <id>` → generates `situation_ru` + `task_ru` (the card front; GPT→Claude).
- Cover (MATCH THE FAMILY — don't just call the stock helper). The prod cover style is a cinematic editorial PHOTO of two execs across a table (one back-to-camera + one facing camera), warm moody glass-walled office, shallow DoF, desk props, with the batch accent colour woven in (`cover.accent_for(batch_id)` = palette[id%5]). Two traps with the stock `content._maybe_generate_cover`: (a) the v2 prompt renders the literal `subtitle`, but our subtitles are ABSTRACT mnemonic scenes (e.g. «Фиолетовый свёрток» → a literal purple parcel, off-style); (b) the current v2 prompt forbids visible faces, but the sibling covers show faces. So HAND-WRITE a prompt describing a realistic scene that fits the topic (face-visible counterpart + back-to-camera foreground + an accent-colour prop) and run: `st=get_settings(); data = cover._request_image(prompt, st.image_model, st.cover_size, st.cover_quality); cover._save_cover_jpeg(data, st.covers_dir / f"{slug}.v2.jpg")`. Pull the JPEG and eyeball it against an existing cover before declaring done.

## 7. Verify + show
- Query: phrase count = 10, mnemo spans = 10/10, all phrases have situation_ru/task_ru, cover_path set.
- Fetch the cover from `english_app:/srv/backend/data/covers/<slug>.v2.jpg` and `SendUserFile` it.
- The batch appears in the app/web under its section automatically (no rebuild). Optionally add es/de/fr `gloss_i18n` / `title_i18n` etc.

Notes: data volume `english_data` → `/srv/backend/data`; deploy/refs in memory `batch-authoring-and-prod-drift`. Keep phrases real and meaning-scored-friendly (don't reward phrasing the grader won't).
