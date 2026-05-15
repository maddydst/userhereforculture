#!/usr/bin/env python3
"""Génère les visuels pour tous les articles dans newsletters.json."""

import hashlib
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_FILE = Path("newsletters.json")
IMAGES_DIR  = Path("generated_images")
IMAGES_DIR.mkdir(exist_ok=True)

THEMES = {
    "Tech":    {"bg": (5, 10, 30),    "accent": (0, 212, 255),   "mid": (0, 80, 140)},
    "Finance": {"bg": (15, 10, 0),    "accent": (212, 175, 55),  "mid": (120, 80, 0)},
    "IA":      {"bg": (15, 0, 30),    "accent": (180, 80, 255),  "mid": (90, 20, 150)},
    "Marché":  {"bg": (20, 10, 0),    "accent": (255, 140, 0),   "mid": (150, 60, 0)},
    "Startup": {"bg": (0, 20, 20),    "accent": (0, 229, 204),   "mid": (0, 110, 100)},
    "Crypto":  {"bg": (20, 12, 0),    "accent": (247, 147, 26),  "mid": (140, 70, 0)},
    "Autre":   {"bg": (10, 10, 20),   "accent": (136, 146, 176), "mid": (60, 65, 90)},
}

W, H = 800, 450


def card_id(titre: str) -> str:
    return hashlib.md5(titre.encode()).hexdigest()[:10]


def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_image(titre: str, categorie: str, seed: int) -> Image.Image:
    theme = THEMES.get(categorie, THEMES["Autre"])
    bg, accent, mid = theme["bg"], theme["accent"], theme["mid"]
    rng = random.Random(seed)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img, "RGBA")

    # Gradient background
    for y in range(H):
        t = y / H
        c = lerp_color(bg, tuple(min(v + 15, 255) for v in bg), t)
        draw.line([(0, y), (W, y)], fill=c)

    # Large blurred circles (glow effect)
    for _ in range(3):
        cx = rng.randint(0, W)
        cy = rng.randint(0, H)
        r  = rng.randint(80, 200)
        for dr in range(r, 0, -3):
            alpha = int(18 * (1 - dr / r))
            draw.ellipse([cx - dr, cy - dr, cx + dr, cy + dr], fill=(*accent, alpha))

    # Geometric shapes
    for _ in range(rng.randint(4, 8)):
        x1 = rng.randint(-20, W)
        y1 = rng.randint(-20, H)
        size = rng.randint(30, 120)
        alpha = rng.randint(12, 35)
        shape = rng.choice(["rect", "circle", "line"])
        if shape == "rect":
            draw.rectangle([x1, y1, x1 + size, y1 + size // 2], outline=(*accent, alpha), width=1)
        elif shape == "circle":
            draw.ellipse([x1, y1, x1 + size, y1 + size], outline=(*accent, alpha), width=1)
        else:
            draw.line([x1, y1, x1 + rng.randint(-100, 100), y1 + rng.randint(-80, 80)],
                      fill=(*accent, alpha), width=1)

    # Grid lines
    for x in range(0, W, 50):
        draw.line([(x, 0), (x, H)], fill=(*accent, 8), width=1)
    for y in range(0, H, 50):
        draw.line([(0, y), (W, y)], fill=(*accent, 8), width=1)

    # Bottom gradient bar
    for i in range(120):
        alpha = int(180 * (i / 120) ** 1.5)
        draw.line([(0, H - 120 + i), (W, H - 120 + i)], fill=(*bg, alpha))

    # Category label
    try:
        font_cat  = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 11)
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception:
        font_cat = font_title = ImageFont.load_default()

    cat_text = categorie.upper()
    draw.text((24, H - 80), cat_text, fill=(*accent, 200), font=font_cat)

    # Title (wrapped)
    words = titre.split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font_title)
        if bbox[2] - bbox[0] > W - 48:
            if line:
                lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    lines = lines[:2]

    y_text = H - 58
    for ln in lines:
        draw.text((24, y_text), ln, fill=(240, 245, 255), font=font_title)
        y_text += 28

    # Top accent line
    draw.rectangle([0, 0, W, 3], fill=accent)

    return img


if not OUTPUT_FILE.exists():
    print("newsletters.json introuvable")
    exit(1)

articles = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
to_process = [a for a in articles if a.get("statut") != "ignore" and a.get("titre")]

print(f"{len(to_process)} articles à traiter\n")
updated = 0

for i, a in enumerate(to_process):
    cid = card_id(a["titre"])
    path = IMAGES_DIR / f"{cid}.png"

    if path.exists() and a.get("image"):
        continue

    img = make_image(a["titre"], a.get("categorie", "Autre"), seed=i)
    img.save(path, format="PNG")
    a["image"] = cid + ".png"
    updated += 1
    print(f"  ✓ {a['titre'][:60]}")

OUTPUT_FILE.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n✓ {updated} image(s) générée(s)")
