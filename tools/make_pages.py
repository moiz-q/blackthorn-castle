"""
Make the web pages for Blackthorn Castle from the original page art.

    python tools/make_pages.py "<folder with 1.png, 2.png, ...>"

For each numbered page it trims any thin black sliver along the edges, brings
the page to 1536 px wide (3:2 pages come out exactly 1536x1024; a page drawn
in another shape keeps that shape) and writes three JPEGs:

    pages/large/001.jpg   1536 wide  - the reader on desktop, and zoom
    pages/small/001.jpg    960 wide  - the reader on phones
    pages/thumb/001.jpg    360 wide  - the contents grid

It also writes assets/pages.js (page list with sizes), the cover picture, the
share picture and the favicon. Needs Pillow and numpy.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WIDTH = 1536
SIZES = {"large": (1536, 84), "small": (960, 80), "thumb": (360, 74)}
MAX_SLIVER = 16


def numbered(src):
    found = []
    for f in src.iterdir():
        m = re.fullmatch(r"(\d+)\.(png|jpe?g|webp)", f.name, re.I)
        if m:
            found.append((int(m.group(1)), f))
    return sorted(found)


def sliver(lines):
    """How many lines at this edge belong to a flat black strip (not dark art).

    A strip is a run of near-black lines that ends in a sharp step up into the
    art; dark art fades in gradually instead. The strip may sit behind a line
    or two of stray light pixels; those go too.
    """
    p95 = [np.percentile(line, 95) for line in lines[:MAX_SLIVER + 3]]
    for start in range(3):
        k = start
        while k < MAX_SLIVER and p95[k] < 32:
            k += 1
        if k - start >= 2:
            step = max(p95[k:k + 3])
            if step > max(60, 2.5 * np.median(p95[start:k])):
                return k
    return 0


def clean(img):
    g = np.asarray(img.convert("L")).astype(int)
    t, b = sliver(g), sliver(g[::-1])
    l, r = sliver(g.T), sliver(g.T[::-1])
    w, h = img.size
    trimmed = (t, b, l, r)
    img = img.crop((l, t, w - r, h - b))

    # Keep the page's drawn shape: a near-3:2 page goes back to exactly 3:2
    # (the trim only nudges it), anything else keeps its own proportions.
    w, h = img.size
    if abs(w / h - 1.5) < 0.03:
        if w / h > 1.5:
            nw = round(h * 1.5)
            img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w / 1.5)
            img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        out = (WIDTH, round(WIDTH / 1.5))
    else:
        out = (WIDTH, round(WIDTH * h / w))
    return img.resize(out, Image.LANCZOS), trimmed


def save(img, path, quality):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=quality, optimize=True, progressive=True)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    listed = numbered(src)
    if not listed:
        sys.exit(f"No numbered pages in {src}")
    numbers = [n for n, _ in listed]
    gaps = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
    if gaps:
        sys.exit(f"Missing page numbers: {gaps}")

    pages = []
    total = 0
    for n, f in listed:
        page, trimmed = clean(Image.open(f).convert("RGB"))
        name = f"{n:03d}.jpg"
        for folder, (w, q) in SIZES.items():
            im = page if w == page.width else page.resize((w, round(w * page.height / page.width)), Image.LANCZOS)
            save(im, ROOT / "pages" / folder / name, q)
        kb = (ROOT / "pages" / "large" / name).stat().st_size // 1024
        total += sum((ROOT / "pages" / d / name).stat().st_size for d in SIZES)
        pages.append({"n": n, "w": page.width, "h": page.height})
        note = f"  trimmed t{trimmed[0]} b{trimmed[1]} l{trimmed[2]} r{trimmed[3]}" if any(trimmed) else ""
        print(f"page {n:>3}: {page.width}x{page.height}  {kb} KB{note}")

    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "pages.js").write_text(
        "window.COMIC = " + json.dumps({"title": "Blackthorn Castle", "chapter": "Chapter 1", "pages": pages}) + ";\n",
        encoding="utf-8",
    )

    first, _ = clean(Image.open(listed[0][1]).convert("RGB"))
    w, h = first.size
    # The cover is page 1 without its page tag (top-left corner).
    cover = first.crop((round(w * 0.07), 0, w, h))
    save(cover.resize((1536, round(1536 * cover.height / cover.width)), Image.LANCZOS), ROOT / "assets" / "cover.jpg", 82)
    share_h = round(w * 630 / 1200)
    share = first.crop((0, (h - share_h) // 2, w, (h - share_h) // 2 + share_h)).resize((1200, 630), Image.LANCZOS)
    save(share, ROOT / "assets" / "share.jpg", 82)
    # Favicon: the castle's central spire, square.
    s = round(h * 0.55)
    icon = first.crop(((w - s) // 2, round(h * 0.08), (w - s) // 2 + s, round(h * 0.08) + s))
    icon.resize((180, 180), Image.LANCZOS).save(ROOT / "assets" / "icon.png", optimize=True)

    print(f"{len(pages)} pages, {total // 1024 // 1024} MB in pages/")


if __name__ == "__main__":
    main()
