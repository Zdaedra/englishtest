"""Second cover set — FEMALE protagonist (D3, #24).

Mirror of _gen_api_covers.py: identical photographic style, same model
(gpt-image-1, 1024x1024, high), only the hero clause flips to a woman. Scenes
come from _covers_female_worklist.tsv (heroine back-to-camera; romantic /
one-on-one counterpart is a man; group scenes stay mixed).

Output: _covers_staged_female/<slug>.v3.png  (raw PNG, like the male staged set;
the .v3.jpg prod derivation + wiring happens after the look is approved).

Usage:
    python _gen_api_covers_female.py                 # all not-yet-generated
    python _gen_api_covers_female.py flirt-1 flirt-2 # only these slugs
    python _gen_api_covers_female.py --group flirt   # a whole group
    FORCE=1 python _gen_api_covers_female.py flirt-1 # regenerate even if exists
"""
import os
import sys
import csv
import time

from app import cover

ROOT = "/Users/daedra/Documents/AI/Claude/english"
OUT = f"{ROOT}/_covers_staged_female"
WL = f"{ROOT}/_covers_female_worklist.tsv"

# Mirrors _gen_api_covers.py TPL verbatim; only the hero clause is feminine so
# lighting / lens / grade / "премиальная редакционная фотография" match exactly.
TPL = ("Фотореалистичная квадратная фотография 1:1, без текста и надписей. {scene}. "
       "Главная героиня — женщина — спиной к камере на переднем плане, чуть подалась вперёд, "
       "внимательная открытая поза. Тёплый мягкий кинематографичный свет, неглубокая резкость "
       "и боке, естественные тона кожи, премиальная редакционная фотография, реалистичная анатомия.")

FORCE = os.environ.get("FORCE") == "1"


def _wanted(argv: list[str]) -> set[str] | None:
    """Return the slug filter, or None for 'all'. Supports `--group <name>`."""
    if not argv:
        return None
    if argv[0] == "--group":
        want_group = argv[1]
        with open(WL) as f:
            return {r["slug"] for r in csv.DictReader(f, delimiter="\t")
                    if r["group"] == want_group}
    return set(argv)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    want = _wanted(sys.argv[1:])

    rows = []
    with open(WL) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            slug = r["slug"]
            if want is not None and slug not in want:
                continue
            dest = f"{OUT}/{slug}.v3.png"
            if os.path.exists(dest) and os.path.getsize(dest) > 0 and not FORCE:
                print(f"SKIP {slug} (exists)", flush=True)
                continue
            rows.append((slug, r["scene_ru"]))

    print(f"to generate: {len(rows)}", flush=True)
    ok = fail = 0
    for i, (slug, scene) in enumerate(rows, 1):
        prompt = TPL.format(scene=scene)
        for attempt in (1, 2):
            try:
                data = cover._request_image(prompt, "gpt-image-1", "1024x1024", "high")
                with open(f"{OUT}/{slug}.v3.png", "wb") as fh:
                    fh.write(data)
                print(f"[{i}/{len(rows)}] OK {slug}: {len(data)} bytes", flush=True)
                ok += 1
                break
            except Exception as e:  # noqa: BLE001 — log & retry, never abort the batch
                print(f"[{i}/{len(rows)}] FAIL {slug} (try {attempt}): {str(e)[:160]}",
                      flush=True)
                if attempt == 2:
                    fail += 1
                else:
                    time.sleep(5)
    print(f"DONE ok={ok} fail={fail}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
