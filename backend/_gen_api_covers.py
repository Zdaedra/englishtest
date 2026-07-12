import os, sys, csv, time
from app import cover

OUT = "/Users/daedra/Documents/AI/Claude/english/_covers_staged"
WL = "/Users/daedra/Documents/AI/Claude/english/_covers_worklist.tsv"
DONE = {"flirt-1", "batch-2", "batch-3", "charisma-1", "stage-11"}  # already generated

TPL = ("Фотореалистичная квадратная фотография 1:1, без текста и надписей. {scene}. "
       "Главный герой — мужчина — спиной к камере на переднем плане, чуть подался вперёд, "
       "внимательная открытая поза. Тёплый мягкий кинематографичный свет, неглубокая резкость "
       "и боке, естественные тона кожи, премиальная редакционная фотография, реалистичная анатомия.")

rows = []
with open(WL) as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["slug"] in DONE:
            continue
        if os.path.exists(f"{OUT}/{r['slug']}.v2.png"):
            print(f"SKIP {r['slug']} (exists)", flush=True)
            continue
        rows.append((r["slug"], r["scene_ru"]))

print(f"to generate: {len(rows)}", flush=True)
ok = fail = 0
for i, (slug, scene) in enumerate(rows, 1):
    for attempt in (1, 2):
        try:
            data = cover._request_image(TPL.format(scene=scene), "gpt-image-1", "1024x1024", "high")
            open(f"{OUT}/{slug}.v2.png", "wb").write(data)
            print(f"[{i}/{len(rows)}] OK {slug}: {len(data)} bytes", flush=True)
            ok += 1
            break
        except Exception as e:
            print(f"[{i}/{len(rows)}] FAIL {slug} (try {attempt}): {str(e)[:160]}", flush=True)
            if attempt == 2:
                fail += 1
            else:
                time.sleep(5)
print(f"DONE ok={ok} fail={fail}", flush=True)
