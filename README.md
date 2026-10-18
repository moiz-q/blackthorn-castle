# Blackthorn Castle

A web comic. Chapter 1, 45 pages.

Read it at **https://moiz-q.github.io/blackthorn-castle/**

## Layout

- `index.html` — cover and contents
- `read.html` — the reader (`read.html#12` opens page 12)
- `pages/large`, `pages/small`, `pages/thumb` — each page at 1536, 960 and 360 px wide
- `assets/` — styles, reader script, page list, cover and share pictures
- `tools/make_pages.py` — makes everything in `pages/` and `assets/pages.js` from the original page art

## Adding or replacing pages

Put the original art in a folder as `1.png`, `2.png`, … and run:

```
python tools/make_pages.py "<that folder>"
```

Then commit and push; the site updates in a minute or two.
