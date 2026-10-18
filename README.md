# Blackthorn Castle

A web comic.

Read it at **https://moiz-q.github.io/blackthorn-castle/**

## Layout

- `index.html`: the cover and every chapter's pages
- `read.html`: the reader (`read.html#12` is chapter 1, page 12; `read.html#2/5` is chapter 2, page 5)
- `publish.html`: "Add a chapter", the page that sends people to the chapter form
- `chapters/<n>/large`, `small`, `thumb`: each page at 1536, 960 and 360 px wide
- `chapters/chapters.json`: the chapters, their titles, credits and page sizes (`assets/comic.js` is made from it)
- `tools/make_pages.py`: builds a chapter from its page art
- `tools/chapter_from_issue.py` and `.github/`: build a chapter from the "New chapter" form

## Adding a chapter

**Through the site:** anyone can use *Add a chapter* (`publish.html`). It opens a GitHub form
where they attach their pages. A workflow builds the chapter, replies with every page numbered,
and opens a pull request. Chapters from the owner and collaborators are merged and go live at
once; anyone else's go live when the owner merges the pull request.

**By hand:** put the pages in a folder as `1.png`, `2.png`, … and run

```
python tools/make_pages.py "<that folder>" --chapter 2 --title "The Cellar" --by "Name"
```

then commit and push. The site updates a minute or two after a push.
