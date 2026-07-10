"""Convert the staged female PNGs -> prod-style JPEGs (same _save_cover_jpeg as
the male pipeline: <=1000px, q82). Writes to a deploy-staging dir AND the local
dev covers dir so the gender→cover resolution is testable locally."""
import glob
import os

from app import cover
from app.config import get_settings

SRC = "/Users/daedra/Documents/AI/Claude/english/_covers_staged_female"
STG = "/Users/daedra/Documents/AI/Claude/english/_covers_staged_female_jpg"
DEV = str(get_settings().covers_dir)

os.makedirs(STG, exist_ok=True)
pngs = sorted(glob.glob(f"{SRC}/*.v3.png"))
print(f"convert {len(pngs)} pngs -> jpg; dev covers dir = {DEV}", flush=True)
for png in pngs:
    name = os.path.basename(png)[:-4] + ".jpg"   # flirt-1.v3.png -> flirt-1.v3.jpg
    data = open(png, "rb").read()
    cover._save_cover_jpeg(data, f"{STG}/{name}")
    cover._save_cover_jpeg(data, os.path.join(DEV, name))
    print("ok", name, os.path.getsize(f"{STG}/{name}"), "bytes", flush=True)
print("done", flush=True)
