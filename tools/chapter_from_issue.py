"""
Build a chapter from a "New chapter" issue (run by .github/workflows/new-chapter.yml).

Reads the issue form from the ISSUE_BODY environment variable, downloads the
page images (or a .zip of numbered pages) attached to it, and builds the
chapter with make_pages.build_chapter. Writes a reply for the issue to
$RUNNER_TEMP/reply.md ({SHA} is filled in once the pages are committed) and
sets these step outputs: ok, chapter, pages, hold (the "hold for review"
box was ticked).

Who may replace a chapter that is already up: AUTHOR_ROLE is the issue
author's association with the repository (OWNER, MEMBER, COLLABORATOR, ...).
"""

import io
import os
import re
import sys
import traceback
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_pages  # noqa: E402

TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
MAX_PAGES = 300
MAX_DOWNLOAD = 30 * 1024 * 1024
ALLOWED = (
    "https://github.com/user-attachments/assets/",
    "https://github.com/user-attachments/files/",
    "https://user-images.githubusercontent.com/",
    "https://private-user-images.githubusercontent.com/",
)
PAGE_NAME = re.compile(r"(?:.*/)?(\d+)\.(png|jpe?g|webp)", re.I)


class Problem(Exception):
    pass


def sections(body):
    """The issue form's answers, by label."""
    out = {}
    for m in re.finditer(r"^###\s+(.+?)\s*$\n(.*?)(?=^###\s|\Z)", body, re.M | re.S):
        value = m.group(2).strip()
        out[m.group(1).strip().lower()] = "" if value == "_No response_" else value
    return out


def attachments(text):
    """Attached files in the order they appear: (kind, alt, url)."""
    found = []
    pattern = re.compile(
        r"<img\b[^>]*>"                          # <img alt="..." src="...">
        r"|!\[([^\]]*)\]\((\S+?)\)"              # ![alt](url)
        r"|\[([^\]]*)\]\((\S+?)\)"               # [file.zip](url)
        r"|(https://\S+)",                       # a bare link
        re.I,
    )
    for m in pattern.finditer(text):
        if m.group(0).lower().startswith("<img"):
            tag = m.group(0)
            src = re.search(r'\bsrc\s*=\s*"([^"]+)"', tag)
            alt = re.search(r'\balt\s*=\s*"([^"]*)"', tag)
            if src:
                found.append(("image", alt.group(1) if alt else "", src.group(1)))
        elif m.group(2):
            found.append(("image", m.group(1), m.group(2)))
        elif m.group(4):
            found.append(("file", m.group(3), m.group(4)))
        elif m.group(5):
            found.append(("file", "", m.group(5).rstrip(").,>")))
    return [(k, a, u) for k, a, u in found if u.startswith(ALLOWED)]


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "blackthorn-castle-chapter-builder"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise Problem("One of the files is bigger than 30 MB.")
    return data


def open_image(data, what):
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        raise Problem(f"{what} isn't an image I can open. Pages need to be PNG, JPG or WebP.")
    if im.width < 600:
        raise Problem(f"{what} is only {im.width} px wide. Pages need to be at least 600 px wide.")
    return im


def pages_from_zip(data, what):
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise Problem(f"{what} isn't a zip file I can open.")
    numbered = []
    for info in z.infolist():
        if info.is_dir() or "__MACOSX" in info.filename:
            continue
        m = PAGE_NAME.fullmatch(info.filename)
        if m:
            numbered.append((int(m.group(1)), info))
    if not numbered:
        raise Problem(f"{what} has no pages named by number (like 1.png, 2.png).")
    numbered.sort(key=lambda x: x[0])
    nums = [n for n, _ in numbered]
    if len(set(nums)) != len(nums):
        raise Problem(f"{what} has two pages with the same number.")
    missing = sorted(set(range(1, nums[-1] + 1)) - set(nums))
    if missing:
        raise Problem(f"{what} is missing page {', '.join(map(str, missing))}.")
    return [open_image(z.read(info), f"Page {n} in {what}") for n, info in numbered]


def collect(found):
    images = [a for a in found if a[0] == "image"]
    # If every picture is labelled with its page number, go by that; otherwise
    # take them in the order they were dropped in.
    nums = [re.fullmatch(r"\s*(?:page\s*)?(\d+)(?:\.\w+)?\s*", alt, re.I) for _, alt, _ in images]
    if images and len(images) == len(found) and all(nums):
        order = [int(m.group(1)) for m in nums]
        if len(set(order)) == len(order):
            found = [a for _, a in sorted(zip(order, found))]

    pages = []
    for i, (kind, alt, url) in enumerate(found, 1):
        data = download(url)
        name = alt or f"attachment {i}"
        if data[:4] == b"PK\x03\x04":
            pages += pages_from_zip(data, f"“{name}”")
        else:
            pages.append(open_image(data, f"Picture {len(pages) + 1}"))
        if len(pages) > MAX_PAGES:
            raise Problem(f"That's more than {MAX_PAGES} pages for one chapter.")
    return pages


def check_chapter(raw, role):
    m = re.fullmatch(r"\s*(?:chapter\s*)?(\d{1,3})\s*", raw or "", re.I)
    if not m or int(m.group(1)) < 1:
        raise Problem("The chapter number should be a number, like 2.")
    n = int(m.group(1))
    have = [c["n"] for c in make_pages.load_index()["chapters"]]
    nxt = max(have, default=0) + 1
    if n in have and role not in TRUSTED:
        raise Problem(f"Chapter {n} is already up. The next chapter is {nxt}.")
    if n > nxt:
        raise Problem(f"There's no chapter {n - 1} yet, so this would leave a gap. The next chapter is {nxt}.")
    return n


def reply_ok(n, count, repo):
    cols = 4
    cells = []
    for p in range(1, count + 1):
        src = f"https://raw.githubusercontent.com/{repo}/{{SHA}}/chapters/{n}/thumb/{p:03d}.jpg"
        cells.append(f'<td align="center"><img src="{src}" width="180" alt="Page {p}"><br><sub>{p}</sub></td>')
    rows = "\n".join("<tr>" + "".join(cells[i:i + cols]) + "</tr>" for i in range(0, len(cells), cols))
    return (
        f"**Chapter {n} is built: {count} page{'s' if count != 1 else ''}.** Here they are in reading order.\n\n"
        "If anything is out of order or missing, edit your post above and the chapter is rebuilt.\n\n"
        f"<table>\n{rows}\n</table>\n"
    )


def output(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    lines = "".join(f"{k}={v}\n" for k, v in values.items())
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(lines)
    else:
        print(lines, end="")


def main():
    body = os.environ.get("ISSUE_BODY", "")
    role = os.environ.get("AUTHOR_ROLE", "NONE")
    repo = os.environ.get("REPO", "moiz-q/blackthorn-castle")
    reply = Path(os.environ.get("RUNNER_TEMP", ".")) / "reply.md"

    form = sections(body)
    try:
        n = check_chapter(form.get("chapter number", ""), role)
        title = re.sub(r"\s+", " ", form.get("chapter title", ""))[:80]
        by = re.sub(r"\s+", " ", form.get("credit", ""))[:80]
        found = attachments(form.get("pages", ""))
        if not found:
            raise Problem("I couldn't find any pages. Drag the page images (or a .zip of them) into the Pages box.")
        pages = collect(found)
        entry = make_pages.build_chapter(n, pages, title, by)
    except Problem as e:
        reply.write_text(f"**I couldn't build this chapter yet.** {e}\n\nEdit your post above to fix it, and I'll try again.\n", encoding="utf-8")
        output(ok="false")
        return
    except Exception as e:  # a download failing, a broken file
        traceback.print_exc()
        reply.write_text(
            "**I couldn't build this chapter yet.** Something went wrong reading the pages "
            f"({type(e).__name__}). Edit your post to try again, or re-attach the pages.\n",
            encoding="utf-8",
        )
        output(ok="false")
        return

    hold = bool(re.search(r"^\s*-\s*\[[xX]\]", form.get("review", ""), re.M))
    reply.write_text(reply_ok(n, len(entry["pages"]), repo), encoding="utf-8")
    output(ok="true", chapter=n, pages=len(entry["pages"]), hold=str(hold).lower())


if __name__ == "__main__":
    main()
