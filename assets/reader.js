(function () {
  "use strict";

  var COMIC = window.COMIC;
  var chapters = COMIC.chapters;
  var many = chapters.length > 1;

  // Every place the reader can be, in order: each chapter's pages, then that
  // chapter's "End of Chapter" screen.
  var stops = [];
  chapters.forEach(function (ch) {
    ch.pages.forEach(function (pg, i) { stops.push({ ch: ch, p: i + 1, w: pg.w, h: pg.h }); });
    stops.push({ ch: ch, end: true });
  });

  var $ = function (id) { return document.getElementById(id); };
  var stage = $("stage"), img = $("page"), end = $("end");
  var prevBtn = $("prev"), nextBtn = $("next"), sidePrev = $("sidePrev"), sideNext = $("sideNext");
  var jump = $("jump"), progress = $("progress"), chapterLabel = $("chapterLabel");
  var zoom = $("zoom"), zoomImg = $("zoomImg");

  var current = -1;
  var cache = {};

  function nn(n) { return String(n).padStart(3, "0"); }
  function src(s, size) { return "chapters/" + s.ch.n + "/" + size + "/" + nn(s.p) + ".jpg"; }
  function chapterName(ch) { return "Chapter " + ch.n; }

  // Chapter 1 keeps its short links (#12); later chapters are #2/5.
  function hashFor(s) {
    if (s.end) return s.ch.n === 1 ? "#end" : "#" + s.ch.n + "/end";
    return s.ch.n === 1 ? "#" + s.p : "#" + s.ch.n + "/" + s.p;
  }

  function find(c, p) {
    for (var i = 0; i < stops.length; i++) {
      var s = stops[i];
      if (s.ch.n !== c) continue;
      if (p === "end" ? s.end : s.p === p) return i;
    }
    return -1;
  }

  function parse() {
    var h = location.hash.replace(/^#\/?/, "").toLowerCase();
    var m = h.match(/^(\d+)\/(\d+|end)$/);
    var i = -1;
    if (m) i = find(parseInt(m[1], 10), m[2] === "end" ? "end" : parseInt(m[2], 10));
    else if (h === "end") i = find(1, "end");
    else if (/^\d+$/.test(h)) i = find(1, parseInt(h, 10));
    return i < 0 ? 0 : i;
  }

  // Phones and small windows get the 960 px page; bigger screens the full one.
  function size() {
    var w = Math.min(stage.clientWidth, stage.clientHeight * 1.5);
    return w * (window.devicePixelRatio || 1) > 1000 ? "large" : "small";
  }

  function preload(i) {
    var s = stops[i];
    if (!s || s.end) return;
    var u = src(s, size());
    if (cache[u]) return;
    var im = new Image();
    im.decoding = "async";
    im.src = u;
    cache[u] = im;
  }

  function text(el, t) { el.textContent = t; }

  function showEnd(s) {
    var i = chapters.indexOf(s.ch), next = chapters[i + 1];
    text($("endKicker"), COMIC.title + (s.ch.title ? " · " + s.ch.title : ""));
    text($("endTitle"), "End of " + chapterName(s.ch));
    text($("endBy"), s.ch.by ? "Pages by " + s.ch.by : "");
    $("endBy").hidden = !s.ch.by;
    var primary = $("endPrimary");
    if (next) {
      primary.href = hashFor(stops[find(next.n, 1)]);
      text(primary, "Start " + chapterName(next));
    } else {
      primary.href = "#1";
      text(primary, "Read from the start");
    }
    document.title = "End of " + chapterName(s.ch) + " · " + COMIC.title;
  }

  function show(i) {
    i = Math.max(0, Math.min(stops.length - 1, i));
    if (i === current) return;
    current = i;
    var s = stops[i];

    var hash = hashFor(s);
    if (location.hash !== hash) history.replaceState(null, "", hash);

    end.hidden = !s.end;
    img.hidden = !!s.end;
    prevBtn.disabled = sidePrev.disabled = i === 0;
    nextBtn.disabled = sideNext.disabled = i === stops.length - 1;
    var count = s.ch.pages.length;
    progress.style.width = (s.end ? 1 : s.p / count) * 100 + "%";
    jump.value = String(s.end ? i - 1 : i);
    text(chapterLabel, chapterName(s.ch) + (s.ch.title ? " · " + s.ch.title : ""));
    try { localStorage.setItem("bc-at", hash); } catch (e) {}

    if (s.end) {
      img.removeAttribute("src"); // so the last page doesn't flash before the next chapter's first
      showEnd(s);
      preload(i + 1);
      return;
    }

    var u = src(s, size());
    img.width = s.w;
    img.height = s.h;
    img.alt = COMIC.title + ", " + chapterName(s.ch) + ", page " + s.p;
    if (img.getAttribute("src") !== u) {
      img.classList.add("loading");
      img.onload = img.onerror = function () { img.classList.remove("loading"); };
      img.src = u;
    }
    document.title = (many ? chapterName(s.ch) + ", page " : "Page ") + s.p + " · " + COMIC.title;

    preload(i + 1);
    preload(i + 2);
    preload(i - 1);
  }

  function go(d) { if (zoom.hidden) show(current + d); }

  // Page menu, grouped by chapter when there is more than one.
  var opts = "";
  chapters.forEach(function (ch) {
    var count = ch.pages.length;
    if (many) opts += '<optgroup label="' + chapterName(ch) + '">';
    stops.forEach(function (s, i) {
      if (s.ch !== ch || s.end) return;
      opts += '<option value="' + i + '">' + (many ? "Ch " + ch.n + " · " : "") + s.p + " / " + count + "</option>";
    });
    if (many) opts += "</optgroup>";
  });
  jump.innerHTML = opts;
  jump.addEventListener("change", function () { show(parseInt(jump.value, 10)); jump.blur(); });

  prevBtn.addEventListener("click", function () { go(-1); });
  nextBtn.addEventListener("click", function () { go(1); });
  sidePrev.addEventListener("click", function () { go(-1); });
  sideNext.addEventListener("click", function () { go(1); });
  window.addEventListener("hashchange", function () { show(parse()); });

  // Keys
  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.target === jump) return;
    if (!zoom.hidden) {
      if (e.key === "Escape") { closeZoom(); e.preventDefault(); }
      return;
    }
    switch (e.key) {
      case "ArrowRight": case "PageDown": case "d": go(1); break;
      case "ArrowLeft": case "PageUp": case "a": go(-1); break;
      case "Home": show(0); break;
      case "End": show(stops.length - 2); break;
      default: return;
    }
    e.preventDefault();
  });

  // Swipe
  var sx = 0, sy = 0, st = 0, multi = false, swiped = 0;
  stage.addEventListener("touchstart", function (e) {
    multi = e.touches.length > 1;
    var t = e.touches[0];
    sx = t.clientX; sy = t.clientY; st = Date.now();
  }, { passive: true });
  stage.addEventListener("touchmove", function (e) {
    if (e.touches.length > 1) multi = true;
  }, { passive: true });
  stage.addEventListener("touchend", function (e) {
    if (multi) return;
    if (window.visualViewport && window.visualViewport.scale > 1.05) return; // pinch-zoomed: let them pan
    var t = e.changedTouches[0];
    var dx = t.clientX - sx, dy = t.clientY - sy;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5 && Date.now() - st < 800) {
      swiped = Date.now();
      go(dx < 0 ? 1 : -1);
    }
  });

  // Zoom: tap the page to see it large; tap again (or Esc) to close.
  function openZoom(e) {
    if (Date.now() - swiped < 400) return;
    var s = stops[current];
    var r = img.getBoundingClientRect();
    var vw = window.innerWidth, vh = window.innerHeight;
    var w = Math.round(Math.max(vw, Math.min(r.width * 2.2, s.w * 1.4)));
    var h = Math.round(w * s.h / s.w);
    zoomImg.src = src(s, "large");
    zoomImg.alt = img.alt;
    zoomImg.style.width = w + "px";
    zoomImg.style.height = h + "px";
    zoomImg.style.margin = Math.max(0, (vh - h) / 2) + "px auto";
    zoom.hidden = false;
    document.body.style.overflow = "hidden";
    var fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
    zoom.scrollLeft = fx * w - vw / 2;
    zoom.scrollTop = fy * h - vh / 2;
    zoom.focus();
  }
  function closeZoom() {
    zoom.hidden = true;
    zoomImg.removeAttribute("src");
    document.body.style.overflow = "";
  }
  img.addEventListener("click", openZoom);
  $("zoomClose").addEventListener("click", function (e) { e.stopPropagation(); closeZoom(); });

  // In the zoom, drag with the mouse to look around; a click without a drag closes it.
  var drag = null, moved = false;
  zoom.tabIndex = -1;
  zoom.addEventListener("mousedown", function (e) {
    if (e.button !== 0) return;
    drag = { x: e.clientX, y: e.clientY, l: zoom.scrollLeft, t: zoom.scrollTop };
    moved = false;
    e.preventDefault();
  });
  window.addEventListener("mousemove", function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
    zoom.scrollLeft = drag.l - dx;
    zoom.scrollTop = drag.t - dy;
  });
  window.addEventListener("mouseup", function () { drag = null; });
  zoom.addEventListener("click", function () { if (!moved) closeZoom(); moved = false; });

  show(parse());
})();
