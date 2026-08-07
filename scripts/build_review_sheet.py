#!/usr/bin/env python3
"""Build the Phase-1 native-rater Google Sheet for Executive English.

Reads all backend/content/*.json (801 phrases), joins an English situation
context from backend/check_phrases.json, and creates a Google Sheet with:
  - Tab "Ratings": read-only content cols + rater input (Native/Natural/Presence
    1-5 dropdowns, Verdict Keep/Weak dropdown, Comment). Frozen header + content.
  - Tab "Instructions": HUMAN-ONLY no-AI rule + rating rubric.

Rating only — NO rewrite column (that's Phase 2). AI-liveness score is NOT shown
(blind human validation).

Reuses the gdrive.py OAuth token. Prints the spreadsheet URL + coverage stats.
"""
import os, re, glob, json, sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE = Path("/Users/daedra/Documents/AI/Claude/english")
CONTENT = BASE / "backend" / "content"
CHECK = BASE / "backend" / "check_phrases.json"
TOKEN = os.path.expanduser("~/Documents/AI/Claude/.gcp/oauth_token.json")

HEADERS = ["#", "Section", "Batch", "Zone", "Anchor", "Phrase (EN)",
           "Situation (EN)", "Native 1-5", "Natural 1-5", "Presence 1-5",
           "Verdict", "Comment (why, optional)"]
FROZEN_COLS = 7  # through Situation (EN)

INSTRUCTIONS = [
    ("HUMAN JUDGMENT ONLY — NO AI.", True),
    ("Do NOT use ChatGPT, Claude, Grammarly-AI or any AI tool to produce or check your ratings.", False),
    ("We have already run extensive AI evaluation. This job exists specifically to capture a real", False),
    ("native executive's ear that AI cannot give. AI-assisted work is detectable and will not be paid.", False),
    ("", False),
    ("WHAT YOU ARE RATING", True),
    ("These are short lines a senior professional says out loud in meetings & negotiations.", False),
    ("For each phrase, read the Situation (EN) it responds to, then score 1-5 on three axes:", False),
    ("", False),
    ("1) NATIVE  — idiomatic, what a native exec actually says, not textbook.", True),
    ("      5 = 'Let me push back on that a little.'   1 = 'I do not agree with your opinion.'", False),
    ("2) NATURAL (spoken)  — flows aloud; contractions, rhythm; not written/formal register.", True),
    ("3) EXECUTIVE PRESENCE  — status & backbone, no hedging/watery filler.", True),
    ("      Strong = 'If you can move on price, I can move on timing.'   Weak = grammar fine but status collapses.", False),
    ("", False),
    ("VERDICT", True),
    ("Set Verdict = Weak when any axis is low / the phrase would make an exec sound off. Otherwise Keep.", False),
    ("Add a one-line WHY in Comment for weak ones (what's off). Do NOT rewrite the phrase — that is a later phase.", False),
    ("", False),
    ("Respect each phrase's Zone (Warm / Backbone / Weight) — that is the intended register; judge within it.", False),
]


def creds():
    c = Credentials.from_authorized_user_file(TOKEN)
    if c.expired and c.refresh_token:
        c.refresh(Request()); open(TOKEN, "w").write(c.to_json())
    return c


def load_rows():
    files = sorted(glob.glob(str(CONTENT / "*.json")),
                   key=lambda p: int(re.match(r"(\d+)", Path(p).name).group(1))
                   if re.match(r"(\d+)", Path(p).name) else 9999)
    rows = []
    for f in files:
        d = json.load(open(f))
        section = d.get("section", "")
        # human-readable batch name from filename: "01-disagreement-ladder.json" -> "Disagreement Ladder"
        stem = re.sub(r"^\d+-", "", Path(f).stem)
        batch_name = stem.replace("-", " ").title()
        for ph in d.get("phrases", []):
            rows.append({"section": section, "batch": batch_name,
                         "zone": ph.get("zone", ""), "anchor": ph.get("anchor", ""),
                         "en": ph.get("en", "")})
    return rows


def load_situations():
    """Resolve an English situation for each phrase.

    check_phrases.json predates the 340 AI replacements, so exact phrase-text
    joins miss them. Recover via phrase-replacements-final.json (new_en ->
    old_anchor) + a (section, anchor) fallback. Reaches 100% coverage.
    """
    data = json.load(open(CHECK))
    exact, by_secanchor, by_anchor = {}, {}, {}
    for r in data:
        st = r.get("stimulus_en", "")
        if not st:
            continue
        tp = r.get("target_phrase_en", "")
        if tp and tp not in exact:
            exact[tp] = st
        by_secanchor.setdefault((r.get("section", ""), r.get("anchor", "")), st)
        by_anchor.setdefault(r.get("anchor", ""), st)

    repl = json.load(open(BASE / "phrase-replacements-final.json")).get("replacements", {})
    new_en_to_old = {}
    for k, v in repl.items():
        old_anchor = k.split("/", 1)[1] if "/" in k else k
        if v.get("new_en"):
            new_en_to_old[v["new_en"]] = old_anchor

    def resolve(row):
        if row["en"] in exact:
            return exact[row["en"]]
        oa = new_en_to_old.get(row["en"])
        if oa:
            if (row["section"], oa) in by_secanchor:
                return by_secanchor[(row["section"], oa)]
            if oa in by_anchor:
                return by_anchor[oa]
        return by_secanchor.get((row["section"], row["anchor"]), "")

    return resolve


def main():
    rows = load_rows()
    resolve = load_situations()
    n = len(rows)
    sits = [resolve(r) for r in rows]
    covered = sum(1 for s in sits if s)
    print(f"Phrases: {n} | situation coverage: {covered}/{n} ({100*covered//n}%)")

    values = [HEADERS]
    for i, (r, s) in enumerate(zip(rows, sits), 1):
        values.append([i, r["section"], r["batch"], r["zone"], r["anchor"],
                       r["en"], s, "", "", "", "", ""])

    c = creds()
    sheets = build("sheets", "v4", credentials=c)

    # 1. create spreadsheet with 2 tabs
    ss = sheets.spreadsheets().create(body={
        "properties": {"title": "Executive English — Phrase Rating (Phase 1, human-only)"},
        "sheets": [
            {"properties": {"sheetId": 0, "title": "Ratings",
                            "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": FROZEN_COLS}}},
            {"properties": {"sheetId": 1, "title": "Instructions"}},
        ],
    }).execute()
    sid = ss["spreadsheetId"]
    url = ss["spreadsheetUrl"]

    # 2. write Ratings values
    sheets.spreadsheets().values().update(
        spreadsheetId=sid, range="Ratings!A1",
        valueInputOption="RAW", body={"values": values}).execute()

    # 3. write Instructions values
    instr = [[t] for t, _ in INSTRUCTIONS]
    sheets.spreadsheets().values().update(
        spreadsheetId=sid, range="Instructions!A1",
        valueInputOption="RAW", body={"values": instr}).execute()

    last = n + 1  # last data row (1-indexed incl header)
    reqs = []
    # bold header row (Ratings)
    reqs.append({"repeatCell": {
        "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
        "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                 "backgroundColor": {"red": .92, "green": .92, "blue": .92}}},
        "fields": "userEnteredFormat(textFormat,backgroundColor)"}})
    # data validation: 1-5 dropdowns on cols H,I,J (idx 7,8,9)
    for col in (7, 8, 9):
        reqs.append({"setDataValidation": {
            "range": {"sheetId": 0, "startRowIndex": 1, "endRowIndex": last,
                      "startColumnIndex": col, "endColumnIndex": col + 1},
            "rule": {"condition": {"type": "ONE_OF_LIST",
                     "values": [{"userEnteredValue": v} for v in ("1", "2", "3", "4", "5")]},
                     "showCustomUi": True, "strict": False}}})
    # Verdict dropdown col K (idx 10)
    reqs.append({"setDataValidation": {
        "range": {"sheetId": 0, "startRowIndex": 1, "endRowIndex": last,
                  "startColumnIndex": 10, "endColumnIndex": 11},
        "rule": {"condition": {"type": "ONE_OF_LIST",
                 "values": [{"userEnteredValue": v} for v in ("Keep", "Weak")]},
                 "showCustomUi": True, "strict": False}}})
    # column widths
    widths = {2: 150, 5: 340, 6: 380, 11: 300}  # Batch, Phrase, Situation, Comment
    for col, w in widths.items():
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": 0, "dimension": "COLUMNS",
                      "startIndex": col, "endIndex": col + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    # wrap Phrase + Situation + Comment
    for col in (5, 6, 11):
        reqs.append({"repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": 1, "endRowIndex": last,
                      "startColumnIndex": col, "endColumnIndex": col + 1},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
            "fields": "userEnteredFormat.wrapStrategy"}})
    # bold title on Instructions A1 + widen col A
    reqs.append({"repeatCell": {
        "range": {"sheetId": 1, "startRowIndex": 0, "endRowIndex": 1},
        "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 12}}},
        "fields": "userEnteredFormat.textFormat"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": 1, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 900}, "fields": "pixelSize"}})
    # bold the section-header lines in Instructions
    for idx, (_, is_bold) in enumerate(INSTRUCTIONS):
        if is_bold:
            reqs.append({"repeatCell": {
                "range": {"sheetId": 1, "startRowIndex": idx, "endRowIndex": idx + 1,
                          "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat"}})

    sheets.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()

    print(f"\n✓ Sheet created")
    print(f"  URL: {url}")
    print(f"  id : {sid}")
    print(f"  rows: {n} phrases + header")


if __name__ == "__main__":
    main()
