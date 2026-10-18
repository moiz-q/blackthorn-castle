"""
Make the web pages for one chapter of Blackthorn Castle from its page art.

    python tools/make_pages.py <folder> --chapter 2 [--title "The Cellar"] [--by "Name"] [--cover]

<folder> holds the chapter's pages named 1.png, 2.png, ... (png, jpg or webp)
in reading order. For each page it trims any thin black sliver along the edges,
brings the page to 1536 px wide (3:2 pages come out exactly 1536x1024; a page
drawn in another shape keeps that shape) and writes three JPEGs:

    chapters/2/large/001.jpg   1536 wide  - the reader on desktop, and zoom
    chapters/2/small/001.jpg    960 wide  - the reader on phones
    chapters/2/thumb/001.jpg    360 wide  - the contents grid

The chapter is then listed in chapters/chapters.json, and assets/comic.js (what
the site reads) is written from that. Rebuilding a chapter replaces it.
--cover also remakes the cover, share picture and favicon from page 1.

Needs Pillow and numpy.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS = ROOT / "chapters"
INDEX = CHAPTERS / "chapters.json"
WIDTH = 1536
SIZES = {"large": (1536, 84), "small": (960, 80), "thumb": (360, 74)}
MAX_SLIVER = 16

Image.MAX_IMAGE_PIXELS = 80_000_000


def numbered(src):
    found = []
    for f in Path(src).iterdir():
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


def load_index():
    if INDEX.exists():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return {"title": "Blackthorn Castle", "chapters": []}


def write_index(index):
    index["chapters"].sort(key=lambda c: c["n"])
    INDEX.parent.mkdir(exist_ok=True)
    INDEX.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "comic.js").write_text(
        "window.COMIC = " + json.dumps(index, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )


def build_chapter(n, images, title="", by="", log=print):
    """Build chapter n from page images given in reading order.

    images: paths or open PIL images. Returns the chapter's index entry.
    """
    out = CHAPTERS / str(n)
    if out.exists():
        shutil.rmtree(out)

    pages = []
    for i, src in enumerate(images, 1):
        im = src if isinstance(src, Image.Image) else Image.open(src)
        page, trimmed = clean(im.convert("RGB"))
        name = f"{i:03d}.jpg"
        for folder, (w, q) in SIZES.items():
            sized = page if w == page.width else page.resize((w, round(w * page.height / page.width)), Image.LANCZOS)
            save(sized, out / folder / name, q)
        pages.append({"w": page.width, "h": page.height})
        kb = (out / "large" / name).stat().st_size // 1024
        note = f"  trimmed t{trimmed[0]} b{trimmed[1]} l{trimmed[2]} r{trimmed[3]}" if any(trimmed) else ""
        log(f"page {i:>3}: {page.width}x{page.height}  {kb} KB{note}")

    entry = {"n": n, "title": title.strip(), "by": by.strip(), "pages": pages}
    index = load_index()
    index["chapters"] = [c for c in index["chapters"] if c["n"] != n] + [entry]
    write_index(index)
    return entry


def make_cover(page_one):
    first, _ = clean(Image.open(page_one).convert("RGB"))
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


def main():
    ap = argparse.ArgumentParser(description="Make one chapter's web pages.")
    ap.add_argument("folder", help="folder with 1.png, 2.png, ...")
    ap.add_argument("--chapter", type=int, required=True)
    ap.add_argument("--title", default="", help="chapter title, e.g. The Cellar")
    ap.add_argument("--by", default="", help="credit shown with the chapter")
    ap.add_argument("--cover", action="store_true", help="also remake the cover from page 1")
    args = ap.parse_args()

    listed = numbered(args.folder)
    if not listed:
        sys.exit(f"No numbered pages in {args.folder}")
    numbers = [n for n, _ in listed]
    gaps = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
    if gaps:
        sys.exit(f"Missing page numbers: {gaps}")

    entry = build_chapter(args.chapter, [f for _, f in listed], args.title, args.by)
    if args.cover:
        make_cover(listed[0][1])
    print(f"Chapter {args.chapter}: {len(entry['pages'])} pages")


if __name__ == "__main__":
    main()
