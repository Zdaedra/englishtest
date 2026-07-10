"""Build a side-by-side review sheet: male v2 (left) vs new female v3 (right),
one row per slug, with slug + scene label. Lets the user approve the female set
in batches and check the style matches.

Usage:
    python _build_cover_compare.py flirt   /path/out.png
"""
import csv
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/daedra/Documents/AI/Claude/english"
MALE = f"{ROOT}/_covers_staged"            # <slug>.v2.png
FEMALE = f"{ROOT}/_covers_staged_female"   # <slug>.v3.png
WL = f"{ROOT}/_covers_female_worklist.tsv"

TH = 460          # thumbnail edge
GAP = 24
MARGIN = 28
LABEL_H = 66
HEAD_H = 46
BG = (247, 247, 245)
INK = (30, 30, 32)
SUB = (110, 110, 116)


def _font(size, bold=False):
    paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _thumb(path):
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        im = Image.new("RGB", (TH, TH), (225, 225, 228))
        d = ImageDraw.Draw(im)
        d.text((TH // 2 - 40, TH // 2), "нет файла", fill=(150, 150, 150), font=_font(20))
        return im
    return im.resize((TH, TH), Image.LANCZOS)


def main():
    import os
    group = sys.argv[1]
    out = sys.argv[2]
    rows = [r for r in csv.DictReader(open(WL), delimiter="\t")
            if r["group"] == group
            and os.path.exists(f"{FEMALE}/{r['slug']}.v3.png")]  # only ready pairs

    W = MARGIN * 2 + TH * 2 + GAP
    row_h = HEAD_H + LABEL_H + TH + GAP
    H = MARGIN * 2 + HEAD_H + len(rows) * row_h
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)

    f_head = _font(26, bold=True)
    f_slug = _font(24, bold=True)
    f_scene = _font(19)
    f_col = _font(20, bold=True)

    d.text((MARGIN, MARGIN - 4), f"Обложки «для девушек» — {group}: мужской v2 ↔ женский v3",
           fill=INK, font=f_head)

    y = MARGIN + HEAD_H
    for r in rows:
        slug = r["slug"]
        d.text((MARGIN, y + 6), slug, fill=INK, font=f_slug)
        wrapped = textwrap.fill(r["scene_ru"], width=92)
        d.multiline_text((MARGIN + 130, y + 4), wrapped, fill=SUB, font=f_scene, spacing=3)
        yy = y + LABEL_H
        d.text((MARGIN, yy - 22), "МУЖСКОЙ v2", fill=SUB, font=f_col)
        d.text((MARGIN + TH + GAP, yy - 22), "ЖЕНСКИЙ v3", fill=(150, 90, 60), font=f_col)
        canvas.paste(_thumb(f"{MALE}/{slug}.v2.png"), (MARGIN, yy))
        canvas.paste(_thumb(f"{FEMALE}/{slug}.v3.png"), (MARGIN + TH + GAP, yy))
        y += row_h

    canvas.save(out, "JPEG", quality=88, optimize=True)
    print("saved", out, canvas.size)


if __name__ == "__main__":
    main()
